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

    raw_event_type = (payload.get("event_type") or "").strip().lower()
    event_type = raw_event_type or Event.TYPE_CUSTOM

    # Keep hover-like events grouped under the flexible custom bucket.
    if raw_event_type in {"hover", "mouseover", "mouseenter"}:
        event_type = Event.TYPE_CUSTOM

    Event.objects.create(
        session=sess,
        page=page,
        event_type=event_type[:32],
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
    events_qs = Event.objects.filter(occurred_at__gte=since).select_related("page").order_by("-occurred_at")

    # sessions per day (python bucket, DB-agnostic)
    per_day = {}
    for dt in sessions_qs.values_list("started_at", flat=True):
        key = dt.date().isoformat()
        per_day[key] = per_day.get(key, 0) + 1

    top_clicks = (
        events_qs.filter(event_type="click")
        .exclude(element_key="")
        .values("page__slug", "element_key")
        .annotate(total=Count("id"))
        .order_by("-total")[:20]
    )

    total_events = events_qs.count()
    hover_total = 0
    scroll_total = events_qs.filter(event_type=Event.TYPE_SCROLL).count()
    page_rollups = {}
    page_scroll_session_depths = {}

    for event in events_qs:
        page_key = event.page.slug
        rollup = page_rollups.setdefault(page_key, {
            "slug": page_key,
            "title": event.page.title or event.page.slug,
            "events": 0,
            "hovers": 0,
            "scrolls": 0,
        })
        rollup["events"] += 1

        data = event.data or {}
        if event.event_type == Event.TYPE_SCROLL:
            rollup["scrolls"] += 1
            depth = data.get("max_scroll_pct_seen") or data.get("scroll_pct") or 0
            session_depths = page_scroll_session_depths.setdefault(page_key, {})
            session_depths[event.session_id] = max(session_depths.get(event.session_id, 0), depth)
        elif event.event_type == Event.TYPE_CUSTOM and (data.get("custom_type") or "").strip() == "hover":
            rollup["hovers"] += 1
            hover_total += 1

    page_spotlight = []
    for slug, rollup in page_rollups.items():
        session_depths = page_scroll_session_depths.get(slug, {})
        avg_depth = round(sum(session_depths.values()) / len(session_depths), 1) if session_depths else 0
        page_spotlight.append({
            **rollup,
            "avg_scroll_depth": avg_depth,
        })

    page_spotlight = sorted(page_spotlight, key=lambda row: (-row["events"], row["slug"]))[:6]
    scroll_leaders = sorted(
        [row for row in page_spotlight if row["avg_scroll_depth"] > 0],
        key=lambda row: (-row["avg_scroll_depth"], -row["scrolls"], row["slug"])
    )[:5]

    context = {
        "since": since,
        "per_day": sorted(per_day.items()),
        "top_clicks": top_clicks,
        "total_sessions": sessions_qs.count(),
        "total_events": total_events,
        "hover_total": hover_total,
        "scroll_total": scroll_total,
        "page_spotlight": page_spotlight,
        "scroll_leaders": scroll_leaders,
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
    events_qs = Event.objects.filter(page=page, occurred_at__gte=since).order_by("-occurred_at")

    clicks = (
        events_qs.filter(event_type="click")
        .exclude(element_key="")
        .values("element_key")
        .annotate(total=Count("id"))
        .order_by("-total")[:50]
    )

    total_events = events_qs.count()
    sessions_total = sessions_qs.count()
    clicks_total = events_qs.filter(event_type=Event.TYPE_CLICK).count()
    custom_total = events_qs.filter(event_type=Event.TYPE_CUSTOM).count()
    scroll_total = events_qs.filter(event_type=Event.TYPE_SCROLL).count()
    view_total = events_qs.filter(event_type=Event.TYPE_VIEW).count()
    input_total = events_qs.filter(event_type=Event.TYPE_INPUT).count()

    hover_total = 0
    custom_breakdown = {}
    top_targets = {}
    recent_activity = []
    scroll_depth_hits = {10: 0, 25: 0, 50: 0, 75: 0, 90: 0, 100: 0}
    deepest_scroll_by_session = {}

    for event in events_qs:
        data = event.data or {}
        custom_type = (data.get("custom_type") or "").strip()
        interaction_label = custom_type if event.event_type == Event.TYPE_CUSTOM and custom_type else event.event_type
        display_label = interaction_label.replace("_", " ").title()

        if custom_type:
            custom_breakdown[custom_type] = custom_breakdown.get(custom_type, 0) + 1
        if custom_type == "hover":
            hover_total += 1

        target = event.element_key or event.css_selector or "(page)"
        if event.event_type == Event.TYPE_SCROLL:
            scroll_pct = data.get("scroll_pct") or 0
            max_scroll_pct_seen = data.get("max_scroll_pct_seen") or scroll_pct
            target = f"{scroll_pct}% depth"
            deepest_scroll_by_session[event.session_id] = max(
                deepest_scroll_by_session.get(event.session_id, 0),
                max_scroll_pct_seen,
            )
            if scroll_pct in scroll_depth_hits:
                scroll_depth_hits[scroll_pct] += 1
        target_key = f"{interaction_label}:{target}"
        if target_key not in top_targets:
            top_targets[target_key] = {
                "label": display_label,
                "target": target,
                "total": 0,
            }
        top_targets[target_key]["total"] += 1

        detail_bits = []
        if event.text:
            detail_bits.append(event.text[:80])
        if isinstance(data, dict) and data.get("x") is not None and data.get("y") is not None:
            detail_bits.append(f'{data.get("x")}, {data.get("y")}')
        if event.event_type == Event.TYPE_SCROLL and data.get("scroll_pct") is not None:
            detail_bits.append(f'{data.get("scroll_pct")}% reached')

        if len(recent_activity) < 14:
            recent_activity.append({
                "label": display_label,
                "target": target,
                "timestamp": event.occurred_at,
                "detail": " | ".join(detail_bits),
            })

    custom_breakdown_rows = [
        {"label": key.replace("_", " ").title(), "total": total}
        for key, total in sorted(custom_breakdown.items(), key=lambda item: (-item[1], item[0]))
    ]
    top_targets_rows = sorted(top_targets.values(), key=lambda row: (-row["total"], row["label"], row["target"]))[:12]
    active_sessions = sessions_qs.filter(events__occurred_at__gte=since).distinct().count()
    interactions_per_session = round(total_events / sessions_total, 1) if sessions_total else 0
    scroll_session_count = len(deepest_scroll_by_session)
    avg_scroll_depth = round(sum(deepest_scroll_by_session.values()) / scroll_session_count, 1) if scroll_session_count else 0
    deepest_scroll_peak = max(deepest_scroll_by_session.values(), default=0)
    scroll_depth_rows = []
    for milestone in [10, 25, 50, 75, 90, 100]:
        sessions_reached = sum(1 for depth in deepest_scroll_by_session.values() if depth >= milestone)
        reach_pct = round((sessions_reached / sessions_total) * 100) if sessions_total else 0
        scroll_depth_rows.append({
            "milestone": milestone,
            "sessions_reached": sessions_reached,
            "reach_pct": reach_pct,
            "hits": scroll_depth_hits[milestone],
        })

    context = {
        "page": page,
        "since": since,
        "sessions_total": sessions_total,
        "clicks": clicks,
        "total_events": total_events,
        "hover_total": hover_total,
        "active_sessions": active_sessions,
        "interactions_per_session": interactions_per_session,
        "avg_scroll_depth": avg_scroll_depth,
        "deepest_scroll_peak": deepest_scroll_peak,
        "scroll_session_count": scroll_session_count,
        "scroll_depth_rows": scroll_depth_rows,
        "event_mix": [
            {"label": "Clicks", "total": clicks_total, "tone": "bg-amber-200 text-amber-900"},
            {"label": "Hovers", "total": hover_total, "tone": "bg-sky-200 text-sky-900"},
            {"label": "Custom", "total": custom_total, "tone": "bg-violet-200 text-violet-900"},
            {"label": "Views", "total": view_total, "tone": "bg-emerald-200 text-emerald-900"},
            {"label": "Scrolls", "total": scroll_total, "tone": "bg-rose-200 text-rose-900"},
            {"label": "Inputs", "total": input_total, "tone": "bg-slate-200 text-slate-900"},
        ],
        "custom_breakdown": custom_breakdown_rows,
        "top_targets": top_targets_rows,
        "recent_activity": recent_activity,
    }
    return render(request, "base/dashboard/dashboard_page_detail.html", context)
