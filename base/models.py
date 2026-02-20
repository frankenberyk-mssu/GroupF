from django.db import models


class Page(models.Model):
    """
    A test page / layout target you track.
    Think: "Homepage v3", "Landing page A", etc.
    """
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200, blank=True)

    raw_html = models.TextField(blank=True, default="")  # <- add this

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or self.slug



class PageVariant(models.Model):
    """
    Optional: if a Page can have multiple layouts/variants (A/B/C).
    Not sure if will use this but staging it here just in case
    """
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="variants")
    key = models.SlugField()  # "a", "b", "v1", "layout-hero-left", etc
    name = models.CharField(max_length=200, blank=True)

    # store the "layout definition" however you want:
    # - a template name
    # - or JSON layout config
    template_name = models.CharField(max_length=200, blank=True)
    layout_json = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("page", "key")]

    def __str__(self):
        return f"{self.page.slug}:{self.key}"


class VisitSession(models.Model):
    """
    One browser visit to a specific Page (and optionally a Variant).
    """
    session_key = models.CharField(max_length=64, db_index=True)  # your own UUID/opaque key
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="sessions")
    variant = models.ForeignKey(
        PageVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions"
    )


    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # attribution / context
    referrer = models.CharField(max_length=500, blank=True)
    landing_url = models.CharField(max_length=800, blank=True)  # full URL with querystring, might use this?
    utm = models.JSONField(default=dict, blank=True)            # utm_source, utm_campaign, like mailchimp does etc

    # device-ish metadata (keep it simple now; can normalize later)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_hash = models.CharField(max_length=128, blank=True)  # we can probably hash IP if we want uniqueness w/o storing raw IP

    # viewport info you can set from JS
    viewport = models.JSONField(default=dict, blank=True)  # {"w": 1440, "h": 900, "dpr": 2}

    class Meta:
        indexes = [
            models.Index(fields=["page", "started_at"]),
            models.Index(fields=["variant", "started_at"]),
        ]

    def __str__(self):
        return f"{self.page.slug} [{self.session_key}]"


class Event(models.Model):
    """
    Raw interaction stream: clicks, scrolls, hovers, page visibility, etc.
    We can store the flexible stuff in `data` so you we don't schema-lock too early.
    """
    TYPE_CLICK = "click"
    TYPE_SCROLL = "scroll"
    TYPE_VIEW = "view"
    TYPE_INPUT = "input"
    TYPE_CUSTOM = "custom"

    EVENT_TYPES = [
        (TYPE_CLICK, "Click"),
        (TYPE_SCROLL, "Scroll"),
        (TYPE_VIEW, "View"),
        (TYPE_INPUT, "Input"),
        (TYPE_CUSTOM, "Custom"),
    ]

    session = models.ForeignKey(VisitSession, on_delete=models.CASCADE, related_name="events")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="events")

    event_type = models.CharField(max_length=32, choices=EVENT_TYPES, db_index=True)
    occurred_at = models.DateTimeField(db_index=True)

    # simple targeting identifiers (optional, but handy)
    element_key = models.CharField(max_length=200, blank=True)  # your stable key like "hero_cta"
    css_selector = models.CharField(max_length=500, blank=True) # fallback way
    text = models.CharField(max_length=300, blank=True)         # clicked text, etc

    # flexible payload:
    # click: {"x": 123, "y": 456, "button": 0}
    # scroll: {"scrollY": 1200, "maxScrollY": 5400}
    # view: {"visible": true, "duration_ms": 5230}
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["page", "event_type", "occurred_at"]),
            models.Index(fields=["session", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.occurred_at}"


class Goal(models.Model):
    """
    A “target interaction” definition, e.g.:
    - Click element_key == "hero_cta"
    - Scroll depth >= 75%
    - Custom event name == "signup_submitted"
    """
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="goals")
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    # simplest: define matching rules as JSON (we can grow into a rule builder later if we want!)
    # Example:
    # {"event_type":"click","element_key":"hero_cta"}
    # {"event_type":"scroll","min_scroll_pct":75}
    rule = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("page", "name")]

    def __str__(self):
        return f"{self.page.slug}: {self.name}"


class Conversion(models.Model):
    """
    When a session satisfies a Goal (precomputed).
    If we don't do this we are going to be scanning raw events every time, very slow, slow is bad
    """
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="conversions")
    session = models.ForeignKey(VisitSession, on_delete=models.CASCADE, related_name="conversions")

    occurred_at = models.DateTimeField(db_index=True)
    details = models.JSONField(default=dict, blank=True)  # snapshot of the triggering event(s)

    class Meta:
        unique_together = [("goal", "session")]
        indexes = [
            models.Index(fields=["goal", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.goal} [{self.session.session_key}]"




# Optional “nice to have later” models, adding so I don't forget but don't need for MVP

class SessionSummary(models.Model):
    """
    Pre-aggregated metrics per session (good for dashboards!!).
    """
    session = models.OneToOneField(VisitSession, on_delete=models.CASCADE, related_name="summary")

    duration_ms = models.PositiveIntegerField(default=0)
    max_scroll_pct = models.FloatField(default=0)  # 0..100
    clicks = models.PositiveIntegerField(default=0)

    # free-form rollups?
    rollup = models.JSONField(default=dict, blank=True)

    computed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Summary {self.session.session_key}"