from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from .forms import LiveTVChannelForm
from .models import LiveTVChannel, MobileAdminToken, MobileVideoUpload
from news.models import Article


def next_live_tv_channel(active_channel, channels):
    channels = list(channels)
    if not active_channel or not channels:
        return None
    for index, channel in enumerate(channels):
        if channel.pk == active_channel.pk:
            return channels[(index + 1) % len(channels)]
    return channels[0]


def live_tv_context(active_channel, channels, force_autoplay=False):
    channels = list(channels)
    next_channel = next_live_tv_channel(active_channel, channels)
    latest_news = Article.published.select_related("category", "state", "city")[:6]
    return {
        "active_channel": active_channel,
        "channels": channels,
        "next_channel": next_channel,
        "loop_same_channel": bool(active_channel and next_channel and active_channel.pk == next_channel.pk),
        "force_autoplay": force_autoplay,
        "latest_news": latest_news,
    }


def absolute_media_url(request, file_obj):
    if not file_obj:
        return ""
    return request.build_absolute_uri(file_obj.url)


def ticker_items(channel):
    if not channel or not channel.ticker_text:
        return []
    raw_items = channel.ticker_text.replace("\r", "\n").replace("|", "\n").split("\n")
    return [item.strip() for item in raw_items if item.strip()]


def serialize_channel_for_mobile(request, channel):
    player_type = channel.player_source_type
    stream_url = ""
    youtube_embed_url = ""

    if player_type == LiveTVChannel.SourceType.DIRECT:
        stream_url = absolute_media_url(request, channel.video_file)
    elif player_type == LiveTVChannel.SourceType.HLS:
        stream_url = channel.stream_url
    elif player_type == LiveTVChannel.SourceType.YOUTUBE:
        youtube_embed_url = channel.youtube_embed_url

    return {
        "id": channel.pk,
        "title": channel.title,
        "description": channel.description,
        "headline": channel.headline,
        "lower_third_label": channel.lower_third_label,
        "ticker_label": channel.ticker_label,
        "ticker": ticker_items(channel),
        "player_type": player_type,
        "stream_url": stream_url,
        "youtube_embed_url": youtube_embed_url,
        "poster_image": absolute_media_url(request, channel.poster_image),
        "channel_logo": absolute_media_url(request, channel.channel_logo),
        "is_live": channel.is_live,
        "autoplay": channel.autoplay,
        "web_url": request.build_absolute_uri(channel.get_absolute_url()),
    }


def mobile_api_authorized(request):
    expected_key = getattr(settings, "MOBILE_UPLOAD_API_KEY", "")
    if not expected_key:
        return False

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Token ").removeprefix("Bearer ").strip()
    return token == expected_key or request.POST.get("api_key") == expected_key


def mobile_admin_user(request):
    auth_header = request.headers.get("Authorization", "")
    key = auth_header.removeprefix("Token ").removeprefix("Bearer ").strip()
    if not key:
        return None
    token = MobileAdminToken.objects.select_related("user").filter(key=key).first()
    if not token or not token.user.is_active or not token.user.is_superuser:
        return None
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token.user


def mobile_admin_required(request):
    user = mobile_admin_user(request)
    if not user:
        return None, JsonResponse({"detail": "Admin login required."}, status=401)
    return user, None


def channel_file_url(request, channel, field_name):
    return absolute_media_url(request, getattr(channel, field_name))


def serialize_channel_for_admin(request, channel):
    data = serialize_channel_for_mobile(request, channel)
    data.update(
        {
            "slug": channel.slug,
            "source_type": channel.source_type,
            "youtube_url": channel.youtube_url,
            "display_order": channel.display_order,
            "show_lower_third": channel.show_lower_third,
            "show_ticker": channel.show_ticker,
            "show_channel_logo": channel.show_channel_logo,
            "meta_title": channel.meta_title,
            "meta_description": channel.meta_description,
            "video_file_url": channel_file_url(request, channel, "video_file"),
            "poster_image_url": channel_file_url(request, channel, "poster_image"),
            "channel_logo_url": channel_file_url(request, channel, "channel_logo"),
            "updated_at": channel.updated_at.isoformat(),
        }
    )
    return data


def superuser_required(view_func):
    return login_required(user_passes_test(lambda user: user.is_superuser)(view_func))


def live_tv_home(request):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = channels.first()
    force_autoplay = request.GET.get("autoplay") == "1"
    return render(request, "live_tv/live_tv_home.html", live_tv_context(active_channel, channels, force_autoplay))


def live_tv_detail(request, slug):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = get_object_or_404(channels, slug=slug)
    force_autoplay = request.GET.get("autoplay") == "1"
    return render(request, "live_tv/live_tv_home.html", live_tv_context(active_channel, channels, force_autoplay))


@require_GET
def current_live_tv_api(request):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = channels.filter(is_live=True).first() or channels.first()
    if not active_channel:
        return JsonResponse({"detail": "No active live TV channel found."}, status=404)
    return JsonResponse(serialize_channel_for_mobile(request, active_channel))


@csrf_exempt
@require_POST
def mobile_video_upload_api(request):
    is_admin = bool(mobile_admin_user(request))
    if not is_admin and not getattr(settings, "MOBILE_UPLOAD_API_KEY", ""):
        return JsonResponse({"detail": "Mobile upload API token is not configured."}, status=503)
    if not is_admin and not mobile_api_authorized(request):
        return JsonResponse({"detail": "Invalid mobile upload API token."}, status=403)

    video = request.FILES.get("video")
    title = request.POST.get("title", "").strip()

    if not video:
        return JsonResponse({"detail": "Video file is required."}, status=400)
    if not title:
        title = Path(video.name).stem[:180] or "Mobile video upload"

    upload = MobileVideoUpload.objects.create(
        title=title,
        description=request.POST.get("description", "").strip(),
        video=video,
        uploaded_by_name=request.POST.get("uploaded_by_name", "").strip(),
        uploaded_by_phone=request.POST.get("uploaded_by_phone", "").strip(),
        device_info=request.POST.get("device_info", "").strip()[:220],
    )

    return JsonResponse(
        {
            "id": upload.pk,
            "title": upload.title,
            "status": upload.status,
            "video_url": request.build_absolute_uri(upload.video.url),
        },
        status=201,
    )


@csrf_exempt
@require_POST
def mobile_admin_login_api(request):
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    device_name = request.POST.get("device_name", "Mobile App").strip()

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({"detail": "Invalid username or password."}, status=400)
    if not user.is_active or not user.is_superuser:
        return JsonResponse({"detail": "Only superuser admins can operate Live TV from mobile."}, status=403)

    token = MobileAdminToken.create_for_user(user, device_name=device_name)
    return JsonResponse(
        {
            "token": token.key,
            "user": {
                "id": user.pk,
                "username": user.get_username(),
                "name": user.get_full_name() or user.get_username(),
                "is_superuser": user.is_superuser,
            },
        }
    )


@csrf_exempt
@require_POST
def mobile_admin_logout_api(request):
    auth_header = request.headers.get("Authorization", "")
    key = auth_header.removeprefix("Token ").removeprefix("Bearer ").strip()
    if key:
        MobileAdminToken.objects.filter(key=key).delete()
    return JsonResponse({"ok": True})


@require_GET
def mobile_admin_dashboard_api(request):
    user, error = mobile_admin_required(request)
    if error:
        return error

    channels = LiveTVChannel.objects.all()
    uploads = MobileVideoUpload.objects.all()[:20]
    return JsonResponse(
        {
            "user": {"id": user.pk, "username": user.get_username(), "name": user.get_full_name() or user.get_username()},
            "channels": [serialize_channel_for_admin(request, channel) for channel in channels],
            "mobile_uploads": [
                {
                    "id": upload.pk,
                    "title": upload.title,
                    "description": upload.description,
                    "status": upload.status,
                    "status_label": upload.get_status_display(),
                    "uploaded_by_name": upload.uploaded_by_name,
                    "uploaded_by_phone": upload.uploaded_by_phone,
                    "video_url": request.build_absolute_uri(upload.video.url),
                    "created_at": upload.created_at.isoformat(),
                }
                for upload in uploads
            ],
            "source_types": list(LiveTVChannel.SourceType.values),
        }
    )


@csrf_exempt
@require_POST
def mobile_admin_channel_save_api(request):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    channel_id = request.POST.get("id") or request.POST.get("channel_id")
    instance = LiveTVChannel.objects.filter(pk=channel_id).first() if channel_id else None

    data = request.POST.copy()
    data.setdefault("title", "The Up Media Live TV")
    data.setdefault("source_type", LiveTVChannel.SourceType.YOUTUBE)
    data.setdefault("lower_third_label", "BREAKING NEWS")
    data.setdefault("headline", data.get("title", "The Up Media Live TV"))
    data.setdefault("ticker_label", "TODAY'S NEWS")
    data.setdefault("ticker_text", "")
    data.setdefault("display_order", "0")

    for boolean_field in [
        "is_active",
        "is_live",
        "autoplay",
        "show_lower_third",
        "show_ticker",
        "show_channel_logo",
    ]:
        data[boolean_field] = "on" if data.get(boolean_field) in {"1", "true", "True", "on", "yes"} else ""

    form = LiveTVChannelForm(data, request.FILES, instance=instance)
    if not form.is_valid():
        return JsonResponse({"detail": "Please correct the channel fields.", "errors": form.errors}, status=400)

    channel = form.save()
    return JsonResponse({"channel": serialize_channel_for_admin(request, channel)})


@csrf_exempt
@require_POST
def mobile_admin_channel_delete_api(request, pk):
    _user, error = mobile_admin_required(request)
    if error:
        return error

    channel = get_object_or_404(LiveTVChannel, pk=pk)
    channel.delete()
    return JsonResponse({"ok": True})


@superuser_required
def dashboard(request):
    channels = LiveTVChannel.objects.all()
    selected_id = request.GET.get("edit")
    instance = channels.filter(pk=selected_id).first() if selected_id else None

    if request.method == "POST":
        instance = channels.filter(pk=request.POST.get("channel_id")).first() if request.POST.get("channel_id") else None
        form = LiveTVChannelForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            channel = form.save()
            messages.success(request, "Live TV channel saved.")
            return redirect(f"{request.path}?edit={channel.pk}")
    else:
        form = LiveTVChannelForm(instance=instance)

    preview_channel = instance or channels.first()
    return render(
        request,
        "live_tv/dashboard.html",
        {
            "channels": channels,
            "form": form,
            "selected_channel": instance,
            "preview_channel": preview_channel,
            "mobile_uploads": MobileVideoUpload.objects.all()[:10],
        },
    )


@superuser_required
@require_POST
def delete_channel(request, pk):
    channel = get_object_or_404(LiveTVChannel, pk=pk)
    channel.delete()
    messages.success(request, "Live TV channel deleted.")
    return redirect("live_tv:dashboard")
