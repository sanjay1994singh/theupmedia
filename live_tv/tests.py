from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import LiveTVChannel, LiveTVPlaylistItem, SocialRenderedVideo
from .services import add_uploaded_video_to_live_playlist, calculate_current_playback, enqueue_completed_broadcast_renders, rebuild_live_playlist
from .tasks import process_live_channel_hls_task


class ControlDashboardTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="dashboard-admin",
            email="dashboard@example.com",
            password="test-password",
        )
        self.client.force_login(self.admin)

    @patch("live_tv.views.live_control_dashboard_payload", return_value={"section": "settings"})
    def test_section_endpoint_returns_json(self, _payload):
        response = self.client.get(reverse("live_tv:api_control_dashboard_section", args=["settings"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertTrue(response.json()["ok"])

    @patch("live_tv.views.live_control_dashboard_payload")
    def test_action_url_is_not_captured_as_section(self, payload):
        response = self.client.get(reverse("live_tv:api_control_dashboard_action"))
        self.assertEqual(response.status_code, 405)
        payload.assert_not_called()


class LiveTVHLSTaskTests(TestCase):
    @patch("live_tv.tasks.process_live_channel_hls_task.delay")
    @patch("live_tv.tasks.repair_live_tv_health")
    @patch("live_tv.tasks.convert_live_channel_to_hls", side_effect=RuntimeError("broken upload"))
    def test_failed_upload_does_not_block_next_pending_video(self, _convert, _repair, delay):
        failed_video = LiveTVChannel.objects.create(
            title="Broken",
            slug="broken",
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file="live-tv/videos/broken.mp4",
            hls_status=LiveTVChannel.HLSStatus.PENDING,
            auto_add_to_live=True,
            is_active=True,
        )
        next_video = LiveTVChannel.objects.create(
            title="Next",
            slug="next",
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file="live-tv/videos/next.mp4",
            hls_status=LiveTVChannel.HLSStatus.PENDING,
            auto_add_to_live=True,
            is_active=True,
        )

        process_live_channel_hls_task(failed_video.pk)

        delay.assert_called_once_with(next_video.pk)


class AutoLivePlaylistTests(TestCase):
    def setUp(self):
        LiveTVChannel.objects.all().delete()
        self.main = LiveTVChannel.objects.create(
            title="Test Main Live",
            slug="test-main-live",
            source_type=LiveTVChannel.SourceType.PLAYLIST,
            auto_playlist_enabled=True,
            auto_add_to_live=False,
            target_playlist_duration_seconds=10800,
            is_active=True,
            is_live=True,
        )

    def make_video(self, title, duration=60, **overrides):
        values = {
            "title": title,
            "slug": title.lower().replace(" ", "-"),
            "source_type": LiveTVChannel.SourceType.DIRECT,
            "video_file": f"live-tv/videos/{title.lower().replace(' ', '-')}.mp4",
            "hls_master_url": f"live-tv/hls/{title.lower().replace(' ', '-')}/master.m3u8",
            "hls_status": LiveTVChannel.HLSStatus.COMPLETED,
            "duration": float(duration),
            "duration_seconds": duration,
            "auto_add_to_live": True,
            "is_active": True,
        }
        values.update(overrides)
        return LiveTVChannel.objects.create(**values)

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_direct_video_adds_once_and_main_cannot_reference_itself(self, _exists):
        video = self.make_video("First Video", 90)
        item, created = add_uploaded_video_to_live_playlist(video, self.main)
        duplicate, duplicate_created = add_uploaded_video_to_live_playlist(video, self.main)
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(item.pk, duplicate.pk)
        self.assertEqual(self.main.playlist_items.filter(is_active=True).count(), 1)
        with self.assertRaises(ValidationError):
            LiveTVPlaylistItem(channel=self.main, video=self.main, duration_seconds=60).full_clean()

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_invalid_or_zero_duration_video_is_rejected(self, _exists):
        zero = self.make_video("Zero Video", 0)
        with self.assertRaises(ValidationError):
            add_uploaded_video_to_live_playlist(zero, self.main)
        youtube = self.make_video(
            "Youtube Video",
            60,
            source_type=LiveTVChannel.SourceType.YOUTUBE,
            video_file=None,
            hls_master_url="",
        )
        with self.assertRaises(ValidationError):
            add_uploaded_video_to_live_playlist(youtube, self.main)

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_loop_and_seek_calculation_are_server_time_based(self, _exists):
        first = self.make_video("One", 10)
        second = self.make_video("Two", 20)
        rebuild_live_playlist([first, second], self.main)
        self.main.refresh_from_db()
        cycle = self.main.playlist_cycles.get()
        started_at = timezone.now() - timedelta(seconds=45)
        cycle.starts_at = started_at
        cycle.save(update_fields=["starts_at"])
        state = calculate_current_playback(self.main, at=started_at + timedelta(seconds=45))
        self.assertEqual(state["video"].pk, second.pk)
        self.assertAlmostEqual(state["seek_position"], 5, places=2)

    @patch("live_tv.tasks.render_live_broadcast_video_task.delay")
    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_render_job_is_created_only_after_playlist_item_streamed(self, _exists, delay):
        first = self.make_video("Rendered One", 10)
        second = self.make_video("Rendered Two", 20)
        rebuild_live_playlist([first, second], self.main)
        self.main.refresh_from_db()
        cycle = self.main.playlist_cycles.get()
        started_at = timezone.now() - timedelta(seconds=1)
        cycle.starts_at = started_at
        cycle.save(update_fields=["starts_at"])

        self.assertEqual(SocialRenderedVideo.objects.count(), 0)
        before_finished = calculate_current_playback(self.main, at=started_at + timedelta(seconds=5))
        enqueue_completed_broadcast_renders(self.main, at=started_at + timedelta(seconds=5), state=before_finished)
        self.assertEqual(SocialRenderedVideo.objects.count(), 0)
        delay.assert_not_called()

        after_first = calculate_current_playback(self.main, at=started_at + timedelta(seconds=11))
        enqueue_completed_broadcast_renders(self.main, at=started_at + timedelta(seconds=11), state=after_first)
        self.assertEqual(SocialRenderedVideo.objects.count(), 1)
        job = SocialRenderedVideo.objects.get()
        self.assertEqual(job.source_video_id, first.pk)
        self.assertEqual(job.status, SocialRenderedVideo.Status.PENDING)
        delay.assert_called_once_with(job.pk)

        enqueue_completed_broadcast_renders(self.main, at=started_at + timedelta(seconds=12), state=after_first)
        self.assertEqual(SocialRenderedVideo.objects.count(), 1)
        delay.assert_called_once_with(job.pk)

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_normal_upload_does_not_interrupt_current_cycle(self, _exists):
        first = self.make_video("Current", 120)
        second = self.make_video("Existing Next", 120)
        rebuild_live_playlist([first, second], self.main)
        self.main.refresh_from_db()
        before = calculate_current_playback(self.main)
        new_video = self.make_video("New End", 120)
        add_uploaded_video_to_live_playlist(new_video, self.main)
        after = calculate_current_playback(self.main)
        self.assertEqual(before["video"].pk, after["video"].pk)
        self.assertEqual(before["playlist_version"], after["playlist_version"])
        self.assertTrue(self.main.playlist_cycles.filter(starts_at__gt=timezone.now()).exists())

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_current_api_returns_same_synchronized_state(self, _exists):
        video = self.make_video("API Video", 300)
        rebuild_live_playlist([video], self.main)
        first = self.client.get(reverse("live_tv:api_live_current"))
        second = self.client.get(reverse("live_tv:api_live_current"))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_data = first.json()
        second_data = second.json()
        self.assertTrue(first_data["is_live_synced"])
        self.assertEqual(first_data["video_id"], second_data["video_id"])
        self.assertLess(abs(first_data["seek_position"] - second_data["seek_position"]), 1)
        self.assertTrue(first_data["stream_url"].startswith(("http://", "https://")))

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_target_trim_only_deactivates_playlist_item(self, _exists):
        self.main.target_playlist_duration_seconds = 200
        self.main.save(update_fields=["target_playlist_duration_seconds", "updated_at"])
        first = self.make_video("Old One", 100)
        second = self.make_video("Old Two", 100)
        third = self.make_video("New Three", 100)
        add_uploaded_video_to_live_playlist(first, self.main)
        add_uploaded_video_to_live_playlist(second, self.main)
        add_uploaded_video_to_live_playlist(third, self.main)
        self.assertLessEqual(self.main.playlist_items.filter(is_active=True).count(), 2)
        self.assertTrue(LiveTVChannel.objects.filter(pk=second.pk, video_file__isnull=False).exists())

    @patch("live_tv.management.commands.populate_live_playlist.probe_video", return_value={"duration": 73.4})
    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_populate_command_saves_ffprobe_duration(self, _exists, _probe):
        video = self.make_video("Needs Duration", 0)
        call_command("populate_live_playlist", verbosity=0)
        video.refresh_from_db()
        self.assertEqual(video.duration_seconds, 73)
        self.assertTrue(self.main.playlist_items.filter(video=video, is_active=True).exists())

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_empty_playlist_falls_back_to_direct_source(self, _exists):
        fallback = self.make_video("Fallback", 60)
        response = self.client.get(reverse("live_tv:api_live_current"))
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["is_live"])
        self.assertFalse(data["is_live_synced"])
        self.assertEqual(data["video_id"], fallback.pk)

    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_playlist_protects_source_video_but_channel_delete_keeps_upload(self, _exists):
        video = self.make_video("Protected Upload", 60)
        rebuild_live_playlist([video], self.main)

        with self.assertRaises(ProtectedError):
            video.delete()

        video_pk = video.pk
        self.main.delete()
        self.assertTrue(LiveTVChannel.objects.filter(pk=video_pk).exists())
