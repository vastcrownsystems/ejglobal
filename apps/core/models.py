# apps/core/models.py
from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model for created/updated timestamps.
    Use across all apps for consistency.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
