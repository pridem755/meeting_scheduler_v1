from django.contrib import admin

from .models import Meeting, MeetingAttendance, MeetingSlot


class MeetingSlotInline(admin.TabularInline):
    model = MeetingSlot
    extra = 1


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ["title", "organization", "meeting_type", "status", "availability_deadline"]
    list_filter = ["status", "meeting_type", "organization"]
    search_fields = ["title", "organization__name"]
    inlines = [MeetingSlotInline]


@admin.register(MeetingAttendance)
class MeetingAttendanceAdmin(admin.ModelAdmin):
    list_display = ["meeting", "user", "status", "checked_in_at"]
    list_filter = ["status"]
