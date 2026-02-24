# apps/accounts/models.py
from django.contrib.auth.models import User
from django.db import models

from apps.core.models import TimeStampedModel


class Profile(TimeStampedModel):
    """
    Extends Django's auth user with business-specific fields.
    One-to-one relationship with auth user.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    image = models.ImageField(upload_to="profile_pics/", blank=True, null=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True)

    def __str__(self) -> str:
        return f"Profile({self.user.username})"

    def get_full_name(self):
        """Return user's full name or username"""
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}"
        return self.user.username

    def get_initials(self):
        """Return user's initials"""
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name[0]}{self.user.last_name[0]}".upper()
        return self.user.username[0].upper()
