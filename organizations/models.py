import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    """
    Connects a User to an Organization and carries their role within it.
    Role lives here (not on User) because a user's permissions are a
    property of their relationship to a specific organization.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        EXECUTIVE = "EXECUTIVE", "Executive"
        MEMBER = "MEMBER", "Member"
        GUEST = "GUEST", "Guest"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    position = models.CharField(max_length=100, blank=True, help_text="e.g. President, Secretary")
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "organization")
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name} ({self.role})"
