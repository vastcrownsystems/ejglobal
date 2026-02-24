# apps/receipts/models.py
from django.db import models

from apps.core.models import TimeStampedModel
from apps.orders.models import Order
from apps.sales.models import Store, Register


class ReceiptSequence(TimeStampedModel):
    """
    Receipt numbering control per store (and optionally per register).
    """
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="receipt_sequences")
    register = models.ForeignKey(Register, on_delete=models.PROTECT, null=True, blank=True, related_name="receipt_sequences")

    prefix = models.CharField(max_length=20, default="RCPT")
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "register"], name="unique_receipt_seq_store_register"),
        ]

    def __str__(self) -> str:
        reg = self.register.code if self.register else "ALL"
        return f"{self.store.name}:{reg}:{self.prefix}"


class Receipt(TimeStampedModel):
    """
    One receipt per paid order, with snapshot payload for re-print and audit.
    """
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="receipt")
    receipt_no = models.CharField(max_length=60, unique=True)

    printed_at = models.DateTimeField(null=True, blank=True)
    print_count = models.PositiveIntegerField(default=0)
    payload = models.JSONField(blank=True, null=True)

    def __str__(self) -> str:
        return self.receipt_no
