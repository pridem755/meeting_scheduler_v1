"""
Business logic for the meeting scheduling workflow: scoring proposed
slots, validating state transitions, and confirming a final time.

These functions are deliberately framework-light -- they take model
instances in and return model instances / dataclasses out. No `request`
object is touched here, which is what makes calculate_best_slots()
unit-testable with plain pytest fixtures instead of a full API client.

The golden rule enforced throughout this module: the scoring engine
RECOMMENDS, it never AUTO-DECIDES. Only schedule_meeting() may set
final_start_time / final_end_time / status=SCHEDULED, and it is only ever
called from an explicit admin action.
"""
import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from availability.models import Availability
from notifications.services import (
    notify_meeting_cancelled,
    notify_meeting_created,
    notify_meeting_scheduled,
    schedule_deadline_reminder,
)

from .models import Meeting, MeetingSlot

logger = logging.getLogger(__name__)

VOTE_WEIGHTS = {
    Availability.VoteStatus.AVAILABLE: 1.0,
    Availability.VoteStatus.MAYBE: 0.5,
    Availability.VoteStatus.NOT_AVAILABLE: 0.0,
}


@dataclass
class SlotScoreResult:
    """The scored outcome for a single MeetingSlot."""

    slot: MeetingSlot
    available_count: int
    maybe_count: int
    not_available_count: int
    no_response_count: int
    response_rate: float
    score: float
    percentage_available: float
    required_attendees_ok: bool
    quorum_met: bool
    eligible: bool
    manual_decision_required: bool = False

    def to_dict(self):
        return {
            "slot_id": self.slot.id,
            "start_time": self.slot.start_time,
            "end_time": self.slot.end_time,
            "available_count": self.available_count,
            "maybe_count": self.maybe_count,
            "not_available_count": self.not_available_count,
            "no_response_count": self.no_response_count,
            "response_rate": round(self.response_rate, 2),
            "score": round(self.score, 2),
            "percentage_available": round(self.percentage_available, 2),
            "required_attendees_ok": self.required_attendees_ok,
            "quorum_met": self.quorum_met,
            "eligible": self.eligible,
            "manual_decision_required": self.manual_decision_required,
        }


def get_eligible_member_count(meeting: Meeting) -> int:
    """Number of active members of the meeting's organization (the voting pool)."""
    return meeting.organization.memberships.filter(is_active=True).count()


def calculate_slot_score(meeting: Meeting, slot: MeetingSlot, total_eligible: int) -> SlotScoreResult:
    """
    Scores a single slot from the votes cast against it. Pure read -- no
    writes happen here.
    """
    votes = Availability.objects.filter(slot=slot)

    available_count = votes.filter(status=Availability.VoteStatus.AVAILABLE).count()
    maybe_count = votes.filter(status=Availability.VoteStatus.MAYBE).count()
    not_available_count = votes.filter(status=Availability.VoteStatus.NOT_AVAILABLE).count()
    responded_count = available_count + maybe_count + not_available_count
    no_response_count = max(total_eligible - responded_count, 0)

    score = (
        available_count * VOTE_WEIGHTS[Availability.VoteStatus.AVAILABLE]
        + maybe_count * VOTE_WEIGHTS[Availability.VoteStatus.MAYBE]
    )

    percentage_available = (available_count / total_eligible * 100) if total_eligible else 0.0
    response_rate = (responded_count / total_eligible * 100) if total_eligible else 0.0

    required_attendees_ok = not votes.filter(
        user__in=meeting.required_attendees.all(),
        status=Availability.VoteStatus.NOT_AVAILABLE,
    ).exists()

    quorum_met = True
    if meeting.decision_mode == Meeting.DecisionMode.REQUIRE_QUORUM:
        quorum_met = percentage_available >= meeting.quorum_percentage

    return SlotScoreResult(
        slot=slot,
        available_count=available_count,
        maybe_count=maybe_count,
        not_available_count=not_available_count,
        no_response_count=no_response_count,
        response_rate=response_rate,
        score=score,
        percentage_available=percentage_available,
        required_attendees_ok=required_attendees_ok,
        quorum_met=quorum_met,
        eligible=required_attendees_ok and quorum_met,
    )


def calculate_best_slots(meeting: Meeting) -> list[SlotScoreResult]:
    """
    Ranks every MeetingSlot on `meeting` by weighted availability score.

    Ranking order:
      1. Eligible slots (pass required-attendee + quorum checks) rank
         above ineligible ones, regardless of raw score.
      2. Higher weighted score wins.
      3. Tie -> higher percentage_available wins.
      4. Tie -> earliest start_time wins.
      5. Still tied at the top -> both flagged manual_decision_required,
         left for the admin to break.

    This function NEVER writes to the database and NEVER picks a winner
    on the system's behalf -- it returns a ranked list for a human
    (the meeting organizer) to act on via schedule_meeting().
    """
    total_eligible = get_eligible_member_count(meeting)
    slots = meeting.slots.all()

    results = [calculate_slot_score(meeting, slot, total_eligible) for slot in slots]
    results.sort(key=lambda r: (not r.eligible, -r.score, -r.percentage_available, r.slot.start_time))

    if len(results) >= 2:
        top, runner_up = results[0], results[1]
        if (
            top.eligible == runner_up.eligible
            and top.score == runner_up.score
            and top.percentage_available == runner_up.percentage_available
        ):
            top.manual_decision_required = True
            runner_up.manual_decision_required = True

    return results


def validate_vote_eligibility(meeting: Meeting, user) -> None:
    """
    Raises ValidationError if `user` is not currently allowed to vote on
    `meeting`. Called by availability.services.cast_vote() before any
    write happens.
    """
    if meeting.status != Meeting.Status.OPEN:
        raise ValidationError("Voting is not open for this meeting.")

    if timezone.now() > meeting.availability_deadline:
        raise ValidationError("The availability deadline for this meeting has passed.")

    is_active_member = meeting.organization.memberships.filter(user=user, is_active=True).exists()
    if not is_active_member:
        raise ValidationError("You must be an active member of this organization to vote.")


def open_meeting_voting(meeting: Meeting) -> Meeting:
    """
    Transitions a DRAFT meeting to OPEN, fires the meeting-created
    notification, and schedules a deadline reminder via Resend.
    """
    if meeting.status != Meeting.Status.DRAFT:
        raise ValidationError("Only a DRAFT meeting can be opened for voting.")
    if not meeting.slots.exists():
        raise ValidationError("Add at least one proposed time slot before opening voting.")

    meeting.status = Meeting.Status.OPEN
    meeting.save(update_fields=["status", "updated_at"])

    recipients = [membership.user for membership in meeting.organization.memberships.filter(is_active=True)]
    notify_meeting_created(meeting, recipients)
    schedule_deadline_reminder(meeting, recipients, hours_before=24)

    return meeting


def close_meeting_voting(meeting: Meeting) -> Meeting:
    """Manually closes voting on an OPEN meeting before its deadline (e.g. quorum already reached)."""
    if meeting.status != Meeting.Status.OPEN:
        raise ValidationError("Only an OPEN meeting can be closed.")

    meeting.status = Meeting.Status.CLOSED
    meeting.save(update_fields=["status", "updated_at"])
    return meeting


@transaction.atomic
def schedule_meeting(meeting: Meeting, slot: MeetingSlot, scheduled_by) -> Meeting:
    """
    Locks in `slot` as the meeting's final time. This is the ONLY function
    in the system that may set final_start_time / final_end_time / flip
    status to SCHEDULED -- it represents a human decision becoming final,
    never an automatic outcome of calculate_best_slots().
    """
    if meeting.status == Meeting.Status.SCHEDULED:
        raise ValidationError("This meeting has already been scheduled.")
    if meeting.status == Meeting.Status.CANCELLED:
        raise ValidationError("Cannot schedule a cancelled meeting.")
    if slot.meeting_id != meeting.id:
        raise ValidationError("That slot does not belong to this meeting.")

    meeting.final_start_time = slot.start_time
    meeting.final_end_time = slot.end_time
    meeting.status = Meeting.Status.SCHEDULED
    meeting.save(update_fields=["final_start_time", "final_end_time", "status", "updated_at"])

    logger.info(
        "Meeting scheduled: meeting_id=%s slot_id=%s scheduled_by_id=%s",
        meeting.id, slot.id, getattr(scheduled_by, "id", None),
    )

    recipients = [membership.user for membership in meeting.organization.memberships.filter(is_active=True)]
    notify_meeting_scheduled(meeting, recipients)

    return meeting


@transaction.atomic
def cancel_meeting(meeting: Meeting, cancelled_by) -> Meeting:
    """Cancels a meeting at any stage and notifies all active org members."""
    if meeting.status == Meeting.Status.SCHEDULED:
        logger.warning("Cancelling an already-scheduled meeting: meeting_id=%s", meeting.id)

    meeting.status = Meeting.Status.CANCELLED
    meeting.save(update_fields=["status", "updated_at"])

    recipients = [membership.user for membership in meeting.organization.memberships.filter(is_active=True)]
    notify_meeting_cancelled(meeting, recipients)

    return meeting
