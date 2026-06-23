from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import LiveTVChannelForm
from .models import LiveTVChannel


def superuser_required(view_func):
    return login_required(user_passes_test(lambda user: user.is_superuser)(view_func))


def live_tv_home(request):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = channels.first()
    return render(request, "live_tv/live_tv_home.html", {"active_channel": active_channel, "channels": channels})


def live_tv_detail(request, slug):
    channels = LiveTVChannel.objects.filter(is_active=True)
    active_channel = get_object_or_404(channels, slug=slug)
    return render(request, "live_tv/live_tv_home.html", {"active_channel": active_channel, "channels": channels})


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
