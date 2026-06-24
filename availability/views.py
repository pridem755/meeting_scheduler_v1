from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from meetings.models import Meeting, MeetingSlot

from . import services
from .models import Availability
from .serializers import AvailabilitySerializer, CastVoteInputSerializer


class AvailabilityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only listing of votes. Creation/updates always go through
    `cast-vote` so eligibility rules (deadline, meeting status,
    membership) are enforced on every write, with no back door via a
    generic create/update endpoint.
    """

    serializer_class = AvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Availability.objects.select_related("slot", "user", "meeting")
        meeting_id = self.request.query_params.get("meeting")
        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

    @extend_schema(
        request=CastVoteInputSerializer,
        responses={200: AvailabilitySerializer},
        summary="Submit or update your vote on a single slot",
    )
    @action(detail=False, methods=["post"], url_path="cast-vote")
    def cast_vote(self, request):
        """
        Submits or updates the authenticated user's vote on one slot.
        Acts as an upsert -- calling this again for the same slot just
        overwrites the previous vote. Rejected if voting isn't open, the
        deadline has passed, or the user isn't an active org member.
        """
        input_serializer = CastVoteInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        try:
            slot = MeetingSlot.objects.select_related("meeting").get(id=data["slot_id"])
        except MeetingSlot.DoesNotExist as exc:
            raise NotFound("That slot does not exist.") from exc

        vote = services.cast_vote(
            meeting=slot.meeting,
            slot=slot,
            user=request.user,
            status=data["status"],
            note=data.get("note", ""),
        )
        return Response(AvailabilitySerializer(vote).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={200: AvailabilitySerializer(many=True)},
        summary="List the authenticated user's votes for a given meeting",
    )
    @action(detail=False, methods=["get"], url_path="my-votes")
    def my_votes(self, request):
        """Returns the authenticated user's votes across every slot on a meeting."""
        meeting_id = request.query_params.get("meeting")
        if not meeting_id:
            return Response({"detail": "meeting query param is required."}, status=400)

        try:
            meeting = Meeting.objects.get(id=meeting_id)
        except Meeting.DoesNotExist as exc:
            raise NotFound("That meeting does not exist.") from exc

        votes = services.get_user_votes_for_meeting(meeting, request.user)
        return Response(AvailabilitySerializer(votes, many=True).data)
