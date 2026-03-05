# apps/orders/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order


@receiver(post_save, sender=Order)
def update_customer_stats_on_order_complete(sender, instance, created, **kwargs):
    """
    Automatically update customer statistics when order is completed

    Triggers when:
    - Order status changes to COMPLETED
    - Order has a linked customer
    """
    # Only update if order is completed and has a customer
    if instance.status == 'COMPLETED' and instance.customer:
        # Update customer statistics
        instance.customer.update_stats()