# base/views.py  (MVP: list pages, render raw html, simple track endpoint)

import json
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Page, VisitSession, Event


@require_GET
def page_list(request):
    pages = Page.objects.filter(is_active=True).order_by("slug")
    return render(request, "base/page_list.html", {"pages": pages})


@require_GET
def page_detail(request, slug):
    """
    Renders trusted HTML stored on the Page model.
    Also ensures the visitor has a Django session we can use as the session_key.
    """
    page = get_object_or_404(Page, slug=slug, is_active=True)

    if not request.session.session_key:
        request.session.create()

    context = {
        "page": page,
        "session_key": request.session.session_key,
        "raw_html": mark_safe(page.raw_html),  # TRUSTED (your requirement)
    }
    return render(request, "base/page_detail.html", context)


# TRACKING STUFF

@csrf_exempt
@require_POST
def track_event(request):
    """
    POST /track/event/
    Minimal payload example:
    {
      "page_slug": "home",
      "event_type": "click",
      "element_key": "hero_cta",
      "data": {...}
    }

    Uses Django's built-in session_key as VisitSession.session_key.
    Creates VisitSession on first event.
    """
    if not request.session.session_key:
        request.session.create()

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    page_slug = (payload.get("page_slug") or "").strip()
    if not page_slug:
        return HttpResponseBadRequest("Missing page_slug")

    page = get_object_or_404(Page, slug=page_slug)

    # Keep this minimal for MVP (anonymous sessions)
    sess, _ = VisitSession.objects.get_or_create(
        session_key=request.session.session_key,
        page=page,
    )

    Event.objects.create(
        session=sess,
        page=page,
        event_type=(payload.get("event_type") or "custom")[:32],
        occurred_at=timezone.now(),
        element_key=(payload.get("element_key") or "")[:200],
        css_selector=(payload.get("css_selector") or "")[:500],
        text=(payload.get("text") or "")[:300],
        data=payload.get("data") or {},
    )

    return JsonResponse({"ok": True})




# DASHBOARD STUFF


# base/views.py (dashboard MVP: overview + per-page drilldown)

@staff_member_required
@require_GET
def dashboard_home(request):
    now = timezone.now()
    since = now - timedelta(days=7)

    sessions_qs = VisitSession.objects.filter(started_at__gte=since)

    # sessions per day (python bucket, DB-agnostic)
    per_day = {}
    for dt in sessions_qs.values_list("started_at", flat=True):
        key = dt.date().isoformat()
        per_day[key] = per_day.get(key, 0) + 1

    top_clicks = (
        Event.objects.filter(occurred_at__gte=since, event_type="click")
        .exclude(element_key="")
        .values("page__slug", "element_key")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    context = {
        "since": since,
        "per_day": sorted(per_day.items()),
        "top_clicks": top_clicks,
        "pages": Page.objects.filter(is_active=True).order_by("slug"),
    }
    return render(request, "base/dashboard/dashboard_home.html", context)


@staff_member_required
@require_GET
def dashboard_page_detail(request, page_slug):
    page = get_object_or_404(Page, slug=page_slug)
    now = timezone.now()
    since = now - timedelta(days=14)

    sessions_qs = VisitSession.objects.filter(page=page, started_at__gte=since)

    clicks = (
        Event.objects.filter(page=page, occurred_at__gte=since, event_type="click")
        .exclude(element_key="")
        .values("element_key")
        .annotate(total=Count("id"))
        .order_by("-total")[:50]
    )

    context = {
        "page": page,
        "since": since,
        "sessions_total": sessions_qs.count(),
        "clicks": clicks,
    }
    return render(request, "base/dashboard/dashboard_page_detail.html", context)
