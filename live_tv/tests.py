from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import LiveTVCategory, LiveTVCity, LiveTVChannel, LiveTVPlaylistItem, LiveTVSetting, LiveTVState, LiveTVVideoHeadline, ShortsVideo, SocialRenderedVideo
from .services import add_uploaded_video_to_live_playlist, calculate_current_playback, create_broadcast_render_job, enqueue_completed_broadcast_renders, get_main_live_channel, rebuild_live_playlist, recover_stale_render_jobs
from .tasks import process_live_channel_hls_task
from .views import video_headline_payload


class CeleryQueueRoutingTests(SimpleTestCase):
    def test_hls_and_render_tasks_use_separate_queues(self):
        self.assertEqual(settings.CELERY_TASK_ROUTES["live_tv.process_live_channel_hls"]["queue"], "hls")
        self.assertEqual(settings.CELERY_TASK_ROUTES["live_tv.process_short_hls"]["queue"], "hls")
        self.assertEqual(settings.CELERY_TASK_ROUTES["live_tv.render_social_video"]["queue"], "render")
        self.assertEqual(settings.CELERY_TASK_ROUTES["live_tv.render_live_broadcast_video"]["queue"], "render")


class VideoHeadlineRotationTests(TestCase):
    def test_video_headlines_rotate_every_configured_second_and_repeat(self):
        video = LiveTVChannel.objects.create(
            title="Headline Video",
            slug="headline-video",
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file="live-tv/videos/headline.mp4",
            headline_change_seconds=2,
            repeat_headlines=True,
        )
        for position, text in enumerate(["First", "Second", "Third"]):
            LiveTVVideoHeadline.objects.create(video=video, position=position, text=text)

        self.assertEqual(video_headline_payload(video, 0)["headline"], "First")
        self.assertEqual(video_headline_payload(video, 2.1)["headline"], "Second")
        self.assertEqual(video_headline_payload(video, 4.1)["headline"], "Third")
        self.assertEqual(video_headline_payload(video, 6.1)["headline"], "First")

    def test_headlines_never_mix_between_videos(self):
        first = LiveTVChannel.objects.create(title="First News", slug="first-news")
        second = LiveTVChannel.objects.create(title="Second News", slug="second-news")
        LiveTVVideoHeadline.objects.create(video=first, position=0, text="First-only headline")
        LiveTVVideoHeadline.objects.create(video=second, position=0, text="Second-only headline")

        self.assertEqual(video_headline_payload(first)["headlines"], ["First-only headline"])
        self.assertEqual(video_headline_payload(second)["headlines"], ["Second-only headline"])


class PersistentTickerClockTests(TestCase):
    def test_clock_only_resets_when_ticker_configuration_changes(self):
        setting = LiveTVSetting.get_solo()
        original_started_at = setting.ticker_started_at

        setting.live_label = "ON AIR"
        setting.save()
        setting.refresh_from_db()
        self.assertEqual(setting.ticker_started_at, original_started_at)

        reset_at = original_started_at + timedelta(minutes=5)
        with patch("live_tv.models.timezone.now", return_value=reset_at):
            setting.default_ticker_text = "Updated server ticker"
            setting.save()
        setting.refresh_from_db()
        self.assertEqual(setting.ticker_started_at, reset_at)

    def test_empty_live_api_uses_persistent_server_clock(self):
        setting = LiveTVSetting.get_solo()
        response = self.client.get(reverse("live_tv:api_live_current"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["ticker_started_at"], setting.ticker_started_at.isoformat())
        self.assertIn(setting.ticker_started_at.isoformat(), payload["ticker_clock_key"])
        self.assertGreaterEqual(payload["ticker_offset_seconds"], 0)

    def test_live_badge_sizes_are_exposed_to_clients(self):
        setting = LiveTVSetting.get_solo()
        setting.web_live_badge_size_percent = 75
        setting.mobile_live_badge_size_percent = 60
        setting.save()

        response = self.client.get(reverse("live_tv:api_live_current"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["settings"]["web_live_badge_size_percent"], 75)
        self.assertEqual(payload["settings"]["mobile_live_badge_size_percent"], 60)
        self.assertEqual(setting.web_live_badge_scale, "0.75")

    def test_live_badge_sizes_validate_admin_range(self):
        setting = LiveTVSetting.get_solo()
        setting.web_live_badge_size_percent = 39
        with self.assertRaises(ValidationError):
            setting.full_clean()


class DashboardPermanentPurgeTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="purge-admin",
            email="purge@example.com",
            password="test-password",
        )
        self.client.force_login(self.admin)
        self.temp_media = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.temp_media.cleanup()

    def media_file(self, relative_path, content=b"video"):
        path = Path(self.temp_media.name) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_purge_deletes_files_and_records_but_preserves_folders_and_settings(self):
        main = get_main_live_channel(create=True)
        source_file = self.media_file("live-tv/videos/2026/07/source.mp4")
        hls_file = self.media_file("live-tv/hls/34/360p/segment_00000.ts")
        settings_logo = self.media_file("live-tv/settings/logo.png", b"logo")
        video = LiveTVChannel.objects.create(
            title="Delete me",
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file="live-tv/videos/2026/07/source.mp4",
            hls_status=LiveTVChannel.HLSStatus.COMPLETED,
            hls_master_url="live-tv/hls/34/master.m3u8",
            duration_seconds=60,
            auto_add_to_live=True,
        )
        LiveTVPlaylistItem.objects.create(channel=main, video=video, position=0, duration_seconds=60)
        SocialRenderedVideo.objects.create(
            title="Delete render",
            source_video=video,
            status=SocialRenderedVideo.Status.COMPLETED,
            rendered_video="social-render/rendered/2026/07/render.mp4",
        )
        rendered_file = self.media_file("social-render/rendered/2026/07/render.mp4")

        response = self.client.post(
            reverse("live_tv:api_control_dashboard_action"),
            {"action": "purge_live_tv_video_content", "confirmation": "DELETE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(LiveTVChannel.objects.filter(pk=video.pk).exists())
        self.assertEqual(LiveTVPlaylistItem.objects.count(), 0)
        self.assertEqual(SocialRenderedVideo.objects.count(), 0)
        self.assertFalse(source_file.exists())
        self.assertFalse(hls_file.exists())
        self.assertFalse(rendered_file.exists())
        self.assertTrue(source_file.parent.is_dir())
        self.assertTrue(hls_file.parent.is_dir())
        self.assertTrue(settings_logo.exists())
        self.assertTrue(main.__class__.objects.filter(pk=main.pk).exists())

    def test_purge_refuses_while_hls_processing_is_active(self):
        source_file = self.media_file("live-tv/videos/2026/07/active.mp4")
        video = LiveTVChannel.objects.create(
            title="Active",
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file="live-tv/videos/2026/07/active.mp4",
            hls_status=LiveTVChannel.HLSStatus.PROCESSING,
            auto_add_to_live=True,
        )

        response = self.client.post(
            reverse("live_tv:api_control_dashboard_action"),
            {"action": "purge_live_tv_video_content", "confirmation": "DELETE"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(LiveTVChannel.objects.filter(pk=video.pk).exists())
        self.assertTrue(source_file.exists())


class StaleRenderRecoveryTests(TestCase):
    @patch("live_tv.services.queue_broadcast_render_task")
    def test_orphaned_processing_render_is_requeued(self, queue_task):
        old_time = timezone.now() - timedelta(minutes=20)
        job = SocialRenderedVideo.objects.create(
            title="Orphaned render",
            status=SocialRenderedVideo.Status.PROCESSING,
            progress_percent=19,
            is_active=True,
        )
        SocialRenderedVideo.objects.filter(pk=job.pk).update(updated_at=old_time)

        recovered = recover_stale_render_jobs(at=timezone.now())

        job.refresh_from_db()
        self.assertEqual(recovered, [job.pk])
        self.assertEqual(job.status, SocialRenderedVideo.Status.PENDING)
        self.assertEqual(job.progress_percent, 0)
        self.assertEqual(job.retry_count, 1)
        queue_task.assert_called_once_with(job.pk)


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


class RequiredVideoTaxonomyTests(TestCase):
    def setUp(self):
        self.category = LiveTVCategory.objects.create(name="News", slug="news")
        self.state = LiveTVState.objects.create(name="Uttar Pradesh", slug="uttar-pradesh")
        self.city = LiveTVCity.objects.create(name="Lucknow", slug="lucknow", state=self.state)

    def test_direct_video_requires_category_state_and_city(self):
        video = LiveTVChannel(
            title="Upload",
            slug="upload",
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file="live-tv/videos/upload.mp4",
        )
        with self.assertRaises(ValidationError) as context:
            video.full_clean()
        self.assertIn("category", context.exception.message_dict)
        self.assertIn("state", context.exception.message_dict)
        self.assertIn("city", context.exception.message_dict)

    def test_shorts_requires_category(self):
        short = ShortsVideo(
            title="Short",
            video_file="shorts/short.mp4",
            state=self.state,
            city=self.city,
        )
        with self.assertRaises(ValidationError) as context:
            short.full_clean()
        self.assertIn("category", context.exception.message_dict)

    def test_mobile_meta_marks_all_three_fields_required(self):
        response = self.client.get(reverse("live_tv:api_meta"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["required_fields"]["video_upload"],
            ["category_id", "state_id", "city_id"],
        )
        self.assertEqual(
            response.json()["required_fields"]["shorts_upload"],
            ["category_id", "state_id", "city_id"],
        )


class LiveTVHLSTaskTests(TestCase):
    @patch("live_tv.tasks.process_live_channel_hls_task.delay")
    @patch("live_tv.tasks.repair_live_tv_health")
    @patch("live_tv.tasks.convert_live_channel_to_hls")
    def test_failed_upload_does_not_block_next_pending_video(self, convert, _repair, delay):
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
        def fail_conversion(channel_id):
            LiveTVChannel.objects.filter(pk=channel_id).update(hls_status=LiveTVChannel.HLSStatus.FAILED)
            raise RuntimeError("broken upload")

        convert.side_effect = fail_conversion
        process_live_channel_hls_task(failed_video.pk)

        delay.assert_called_once_with(next_video.pk)

    @patch("live_tv.tasks.process_live_channel_hls_task.delay")
    @patch("live_tv.tasks.repair_live_tv_health")
    @patch("live_tv.tasks.convert_live_channel_to_hls", return_value="")
    def test_lock_skipped_pending_upload_does_not_chain(self, _convert, _repair, delay):
        pending_video = LiveTVChannel.objects.create(
            title="Lock Pending",
            slug="lock-pending",
            source_type=LiveTVChannel.SourceType.DIRECT,
            video_file="live-tv/videos/lock-pending.mp4",
            hls_status=LiveTVChannel.HLSStatus.PENDING,
            auto_add_to_live=True,
            is_active=True,
        )

        process_live_channel_hls_task(pending_video.pk)

        delay.assert_not_called()


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

    @patch("live_tv.services.live_video_hls_ready", return_value=True)
    @patch("django.core.files.storage.FileSystemStorage.exists", return_value=True)
    def test_same_source_video_is_never_rendered_again_in_a_new_cycle(self, _exists, _hls_ready):
        video = self.make_video("Render Once", 10)
        rebuild_live_playlist([video], self.main)
        first_cycle_item = self.main.playlist_cycles.latest("pk").items.get()
        first_job, first_created = create_broadcast_render_job(first_cycle_item)
        self.assertTrue(first_created)
        SocialRenderedVideo.objects.filter(pk=first_job.pk).update(
            status=SocialRenderedVideo.Status.COMPLETED,
            rendered_video="social-render/rendered/render-once.mp4",
            completed_at=timezone.now(),
        )

        rebuild_live_playlist([video], self.main)
        second_cycle_item = self.main.playlist_cycles.latest("pk").items.get()
        reused_job, second_created = create_broadcast_render_job(second_cycle_item)

        self.assertFalse(second_created)
        self.assertEqual(reused_job.pk, first_job.pk)
        self.assertEqual(SocialRenderedVideo.objects.filter(source_video=video).count(), 1)
        self.assertEqual(first_job.render_key, f"live:source:v3:{video.pk}")

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
