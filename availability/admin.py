from django.contrib import admin

from .models import Availability


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ["user", "meeting", "slot", "status", "submitted_at"]
    list_filter = ["status"]
    search_fields = ["user__email", "meeting__title"]
