"""
Business logic for casting and reading availability votes. Eligibility
rules (deadline, meeting status, membership) are delegated to
meetings.services.validate_vote_eligibility() so that rule lives in one
place even though both apps touch it.
"""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from meetings.services import validate_vote_eligibility

from .models import Availability


@transaction.atomic
def cast_vote(meeting, slot, user, status, note="") -> Availability:
    """
    Creates or updates `user`'s vote for `slot` on `meeting`. Upserts on
    the unique_together('slot', 'user') constraint, so calling this twice
    for the same user/slot just overwrites the previous vote.
    """
    if slot.meeting_id != meeting.id:
        raise ValidationError("That slot does not belong to this meeting.")

    validate_vote_eligibility(meeting, user)

    vote, _created = Availability.objects.update_or_create(
        slot=slot,
        user=user,
        defaults={"meeting": meeting, "status": status, "note": note},
    )
    return vote


def get_meeting_votes(meeting):
    """All votes cast for every slot on `meeting`."""
    return Availability.objects.filter(meeting=meeting).select_related("slot", "user")


def get_user_votes_for_meeting(meeting, user):
    """A single user's votes across all slots on `meeting`."""
    return Availability.objects.filter(meeting=meeting, user=user).select_related("slot")
