from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from news.models import Article

from .forms import ShareCampaignForm
from .models import ShareCampaign, ShareDelivery, ShareTarget
from .services import run_campaign


def can_manage_distribution(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


staff_required = user_passes_test(can_manage_distribution)


@staff_required
def dashboard(request):
    campaigns = ShareCampaign.objects.select_related("article", "created_by")[:20]
    targets = ShareTarget.objects.filter(is_active=True)
    return render(request, "distribution/dashboard.html", {"campaigns": campaigns, "targets": targets})


@staff_required
def campaign_create(request):
    article_id = request.GET.get("article")
    initial = {}
    if article_id:
        article = get_object_or_404(Article.published, pk=article_id)
        link = request.build_absolute_uri(article.get_absolute_url())
        initial = {
            "article": article,
            "title": article.title,
            "caption": f"{article.title}\n\n{article.summary}",
            "link": link,
        }
    if request.method == "POST":
        form = ShareCampaignForm(request.POST)
        if form.is_valid():
            form.instance.created_by = request.user
            form.instance.status = ShareCampaign.Status.QUEUED
            campaign = form.save()
            messages.success(request, "Share campaign created.")
            return redirect(campaign.get_absolute_url())
    else:
        form = ShareCampaignForm(initial=initial)
        default_targets = ShareTarget.objects.filter(is_active=True, default_selected=True)
        if default_targets:
            form.fields["targets"].initial = default_targets
    return render(request, "distribution/campaign_form.html", {"form": form})


@staff_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(ShareCampaign.objects.select_related("article"), pk=pk)
    deliveries = campaign.deliveries.select_related("target")
    return render(request, "distribution/campaign_detail.html", {"campaign": campaign, "deliveries": deliveries})


@staff_required
def campaign_run(request, pk):
    campaign = get_object_or_404(ShareCampaign, pk=pk)
    if request.method == "POST":
        run_campaign(campaign)
        messages.success(request, "Campaign processed. WhatsApp group targets are ready as manual share links.")
    return redirect(reverse("distribution:campaign_detail", kwargs={"pk": campaign.pk}))


@staff_required
def target_list(request):
    targets = ShareTarget.objects.all()
    return render(request, "distribution/target_list.html", {"targets": targets})
