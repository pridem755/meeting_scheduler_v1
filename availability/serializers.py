from rest_framework import serializers

from .models import Availability


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = ["id", "meeting", "slot", "user", "status", "note", "submitted_at"]
        read_only_fields = ["id", "user", "submitted_at"]


class CastVoteInputSerializer(serializers.Serializer):
    """Input for POST /availability/cast-vote/."""
    slot_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=Availability.VoteStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)
