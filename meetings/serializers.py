from rest_framework import serializers

from .models import Meeting, MeetingAttendance, MeetingSlot


class MeetingSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingSlot
        fields = ["id", "meeting", "start_time", "end_time", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError("end_time must be after start_time.")
        return attrs


class MeetingSerializer(serializers.ModelSerializer):
    slots = MeetingSlotSerializer(many=True, read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id", "organization", "title", "description", "meeting_type", "location",
            "online_link", "status", "availability_deadline", "decision_mode",
            "quorum_percentage", "required_attendees", "final_start_time", "final_end_time",
            "created_by", "created_at", "updated_at", "slots",
        ]
        read_only_fields = [
            "id", "status", "final_start_time", "final_end_time",
            "created_by", "created_at", "updated_at", "slots",
        ]


class ScheduleMeetingInputSerializer(serializers.Serializer):
    """Input for POST /meetings/{id}/schedule/ -- the admin's final decision."""
    slot_id = serializers.UUIDField()


class SlotScoreResultSerializer(serializers.Serializer):
    """
    Read-only response shape for GET /meetings/{id}/best-slots/.
    Mirrors meetings.services.SlotScoreResult.to_dict() exactly.
    """
    slot_id = serializers.UUIDField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    available_count = serializers.IntegerField()
    maybe_count = serializers.IntegerField()
    not_available_count = serializers.IntegerField()
    no_response_count = serializers.IntegerField()
    response_rate = serializers.FloatField()
    score = serializers.FloatField()
    percentage_available = serializers.FloatField()
    required_attendees_ok = serializers.BooleanField()
    quorum_met = serializers.BooleanField()
    eligible = serializers.BooleanField()
    manual_decision_required = serializers.BooleanField()


class MeetingAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingAttendance
        fields = ["id", "meeting", "user", "status", "checked_in_at"]
        read_only_fields = ["id"]
