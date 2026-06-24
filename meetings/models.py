import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from organizations.models import Organization


class Meeting(models.Model):
    class MeetingType(models.TextChoices):
        GENERAL = "GENERAL", "General"
        EXECUTIVE = "EXECUTIVE", "Executive"
        EVENT_PLANNING = "EVENT_PLANNING", "Event Planning"
        EMERGENCY = "EMERGENCY", "Emergency"
        GUEST_SPEAKER = "GUEST_SPEAKER", "Guest Speaker"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open for availability"
        CLOSED = "CLOSED", "Closed"
        SCHEDULED = "SCHEDULED", "Scheduled"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    class DecisionMode(models.TextChoices):
        SIMPLE_COUNT = "SIMPLE_COUNT", "Simple count"
        WEIGHTED_BY_ROLE = "WEIGHTED_BY_ROLE", "Weighted by role"
        REQUIRE_QUORUM = "REQUIRE_QUORUM", "Require quorum"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="meetings")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    meeting_type = models.CharField(max_length=20, choices=MeetingType.choices, default=MeetingType.GENERAL)
    location = models.CharField(max_length=255, blank=True)
    online_link = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    availability_deadline = models.DateTimeField()
    decision_mode = models.CharField(max_length=20, choices=DecisionMode.choices, default=DecisionMode.SIMPLE_COUNT)
    quorum_percentage = models.PositiveSmallIntegerField(default=60)

    required_attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="required_for_meetings"
    )

    final_start_time = models.DateTimeField(null=True, blank=True)
    final_end_time = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="meetings_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.organization.name})"

    @property
    def is_voting_open(self):
        return self.status == self.Status.OPEN and timezone.now() <= self.availability_deadline


class MeetingSlot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="slots")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]
        unique_together = ("meeting", "start_time", "end_time")

    def __str__(self):
        return f"{self.meeting.title}: {self.start_time:%Y-%m-%d %H:%M} - {self.end_time:%H:%M}"

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("end_time must be after start_time.")


class MeetingAttendance(models.Model):
    class AttendanceStatus(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        EXCUSED = "EXCUSED", "Excused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="attendance_records")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records"
    )
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.ABSENT)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("meeting", "user")
        ordering = ["meeting", "user"]

    def __str__(self):
        return f"{self.user.email} - {self.meeting.title} ({self.status})"
