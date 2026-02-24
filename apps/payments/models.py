# apps/payments/models.py
from django.db import models

from apps.core.models import TimeStampedModel
from apps.orders.models import Order

class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        TRANSFER = "TRANSFER", "Transfer"
        POS = "POS", "POS"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments", related_query_name="payment")
    method = models.CharField(max_length=12, choices=Method.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=64, blank=True)
