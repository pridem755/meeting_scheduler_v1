import logging

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .models import Meeting, MeetingAttendance, MeetingSlot
from .permissions import IsMeetingOrgAdminOrReadOnly
from .serializers import (
    MeetingAttendanceSerializer,
    MeetingSerializer,
    MeetingSlotSerializer,
    ScheduleMeetingInputSerializer,
    SlotScoreResultSerializer,
)

logger = logging.getLogger(__name__)


class MeetingViewSet(viewsets.ModelViewSet):
    """
    CRUD for meetings, plus action endpoints covering the full scheduling
    workflow: open voting, close voting, view ranked recommendations,
    confirm a final time, and cancel.
    """

    queryset = Meeting.objects.select_related("organization", "created_by").prefetch_related("slots")
    serializer_class = MeetingSerializer
    permission_classes = [permissions.IsAuthenticated, IsMeetingOrgAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(responses={200: MeetingSerializer}, summary="Open a DRAFT meeting for member voting")
    @action(detail=True, methods=["post"], url_path="open-voting")
    def open_voting(self, request, pk=None):
        """Transitions a DRAFT meeting to OPEN and notifies all active org members."""
        meeting = self.get_object()
        meeting = services.open_meeting_voting(meeting)
        return Response(MeetingSerializer(meeting).data)

    @extend_schema(responses={200: MeetingSerializer}, summary="Manually close voting before the deadline")
    @action(detail=True, methods=["post"], url_path="close-voting")
    def close_voting(self, request, pk=None):
        """Manually closes voting on an OPEN meeting before its deadline."""
        meeting = self.get_object()
        meeting = services.close_meeting_voting(meeting)
        return Response(MeetingSerializer(meeting).data)

    @extend_schema(
        responses={200: SlotScoreResultSerializer(many=True)},
        summary="Get ranked slot recommendations (read-only, never auto-decides)",
    )
    @action(detail=True, methods=["get"], url_path="best-slots")
    def best_slots(self, request, pk=None):
        """
        Returns every proposed slot ranked by weighted availability score.
        This is a recommendation only -- the meeting organizer still has
        to call `schedule/` to make a final time official.
        """
        meeting = self.get_object()
        results = services.calculate_best_slots(meeting)
        serialized = SlotScoreResultSerializer([r.to_dict() for r in results], many=True)
        return Response(serialized.data)

    @extend_schema(
        request=ScheduleMeetingInputSerializer,
        responses={200: MeetingSerializer},
        summary="Confirm the final meeting time (the only action that locks it in)",
    )
    @action(detail=True, methods=["post"], url_path="schedule")
    def schedule(self, request, pk=None):
        """Confirms a final slot for this meeting -- the human decision becomes final here."""
        meeting = self.get_object()
        input_serializer = ScheduleMeetingInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        slot = MeetingSlot.objects.filter(
            id=input_serializer.validated_data["slot_id"], meeting=meeting
        ).first()
        if slot is None:
            raise ValidationError("That slot does not exist on this meeting.")

        meeting = services.schedule_meeting(meeting, slot, scheduled_by=request.user)
        return Response(MeetingSerializer(meeting).data)

    @extend_schema(responses={200: MeetingSerializer}, summary="Cancel a meeting")
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """Cancels a meeting at any stage and notifies all active org members."""
        meeting = self.get_object()
        meeting = services.cancel_meeting(meeting, cancelled_by=request.user)
        return Response(MeetingSerializer(meeting).data)


class MeetingSlotViewSet(viewsets.ModelViewSet):
    """CRUD for proposed time slots attached to a meeting. Filterable by ?meeting=<uuid>."""

    queryset = MeetingSlot.objects.select_related("meeting")
    serializer_class = MeetingSlotSerializer
    permission_classes = [permissions.IsAuthenticated, IsMeetingOrgAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        meeting_id = self.request.query_params.get("meeting")
        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        return queryset


class MeetingAttendanceViewSet(viewsets.ModelViewSet):
    """Tracks who actually showed up to a scheduled meeting. Filterable by ?meeting=<uuid>."""

    queryset = MeetingAttendance.objects.select_related("meeting", "user")
    serializer_class = MeetingAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsMeetingOrgAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        meeting_id = self.request.query_params.get("meeting")
        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        return queryset
