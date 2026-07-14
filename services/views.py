from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from .models import Service
from subscriptions.models import SubscriptionPlan


def service_list(request):
    plan_qs = SubscriptionPlan.objects.filter(is_active=True).order_by("display_order", "price")
    services = Service.objects.filter(is_active=True).prefetch_related(Prefetch("subscription_plans", queryset=plan_qs, to_attr="active_subscription_plans"))
    featured_services = services.filter(is_featured=True)[:6]
    paginator = Paginator(services, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    template_name = "services/includes/service_results.html" if request.headers.get("x-requested-with") == "XMLHttpRequest" else "services/service_list.html"
    return render(
        request,
        template_name,
        {"page_obj": page_obj, "featured_services": featured_services},
    )


def service_detail(request, slug):
    plan_qs = SubscriptionPlan.objects.filter(is_active=True).order_by("display_order", "price")
    service = get_object_or_404(Service.objects.filter(is_active=True).prefetch_related(Prefetch("subscription_plans", queryset=plan_qs, to_attr="active_subscription_plans")), slug=slug)
    related_services = Service.objects.filter(is_active=True).prefetch_related(Prefetch("subscription_plans", queryset=plan_qs, to_attr="active_subscription_plans")).exclude(pk=service.pk)[:4]
    return render(request, "services/service_detail.html", {"service": service, "related_services": related_services})

# Create your views here.
