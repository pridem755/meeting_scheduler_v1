import uuid

from django.conf import settings
from django.db import models

from meetings.models import Meeting


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        MEETING_CREATED = "MEETING_CREATED", "Meeting created"
        AVAILABILITY_REMINDER = "AVAILABILITY_REMINDER", "Availability reminder"
        MEETING_SCHEDULED = "MEETING_SCHEDULED", "Meeting scheduled"
        MEETING_CANCELLED = "MEETING_CANCELLED", "Meeting cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} -> {self.user.email}"
