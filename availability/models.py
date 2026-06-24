import uuid

from django.conf import settings
from django.db import models

from meetings.models import Meeting, MeetingSlot


class Availability(models.Model):
    """
    A single member's vote on a single proposed slot. One row per
    (slot, user) pair -- the unique_together constraint is what makes
    "update my vote" an upsert rather than a pile of duplicate rows.
    """

    class VoteStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        MAYBE = "MAYBE", "Maybe"
        NOT_AVAILABLE = "NOT_AVAILABLE", "Not available"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="availability_votes")
    slot = models.ForeignKey(MeetingSlot, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="availability_votes"
    )
    status = models.CharField(max_length=20, choices=VoteStatus.choices)
    note = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("slot", "user")
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.user.email} -> {self.slot} : {self.status}"
