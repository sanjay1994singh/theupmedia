from django.shortcuts import get_object_or_404, render

from .models import Service


def service_list(request):
    services = Service.objects.filter(is_active=True)
    featured_services = services.filter(is_featured=True)[:6]
    return render(
        request,
        "services/service_list.html",
        {"services": services, "featured_services": featured_services},
    )


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.filter(is_active=True), slug=slug)
    related_services = Service.objects.filter(is_active=True).exclude(pk=service.pk)[:4]
    return render(request, "services/service_detail.html", {"service": service, "related_services": related_services})

# Create your views here.
