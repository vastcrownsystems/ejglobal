# apps/sales/models.py
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from decimal import Decimal

from apps.core.models import TimeStampedModel


class Store(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Register(TimeStampedModel):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="registers")
    name = models.CharField(max_length=60)  # e.g. "Front Desk 1"
    code = models.CharField(max_length=30, unique=True)  # internal unique code
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["store", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.store.name} - {self.name}"


class CashierSession(TimeStampedModel):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="sessions")
    register = models.ForeignKey(Register, on_delete=models.PROTECT, related_name="sessions")
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cashier_sessions")

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["store", "register", "opened_at"]),
            models.Index(fields=["cashier", "opened_at"]),
            models.Index(fields=["register", "closed_at"]),
        ]
        constraints = [
            # ✅ ensures you cannot have 2 OPEN sessions on same register
            models.UniqueConstraint(
                fields=["register"],
                condition=Q(closed_at__isnull=True),
                name="uniq_open_session_per_register",
            ),
        ]

    def __str__(self) -> str:
        return f"Session({self.cashier} @ {self.register.code} - {self.opened_at:%Y-%m-%d %H:%M})"

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def duration_seconds(self) -> int:
        end = self.closed_at or timezone.now()
        if not self.opened_at:
            return 0
        return int((end - self.opened_at).total_seconds())

    @property
    def duration_display(self) -> str:
        secs = self.duration_seconds
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        return f"{hours}h {minutes}m"

    @property
    def cash_difference(self):
        if self.closing_cash is None:
            return None
        return self.closing_cash - self.opening_cash

    # TEMP until payments are integrated
    @property
    def cash_sales_total(self):
        # later: sum of cash payments linked to this session
        return Decimal("0.00")

    @property
    def expected_cash(self):
        return self.opening_cash + self.cash_sales_total

    @property
    def variance(self):
        if self.closing_cash is None:
            return None
        return self.closing_cash - self.expected_cash
