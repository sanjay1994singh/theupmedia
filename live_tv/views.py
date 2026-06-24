from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import LiveTVChannelForm
from .models import LiveTVChannel
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
        },
    )


@superuser_required
@require_POST
def delete_channel(request, pk):
    channel = get_object_or_404(LiveTVChannel, pk=pk)
    channel.delete()
    messages.success(request, "Live TV channel deleted.")
    return redirect("live_tv:dashboard")
