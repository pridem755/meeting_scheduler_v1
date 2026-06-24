"""
Notification dispatch layer. Two responsibilities, kept deliberately
separate:

  1. Persisting an in-app Notification row (source of truth for the
     notification feed in the UI).
  2. Sending the corresponding email via Resend, optionally scheduled
     for a future send time using Resend's native `scheduled_at` support.

Email sending is always best-effort: a Resend outage must never break the
core scheduling flow (casting a vote, scheduling a meeting), so failures
are logged, not raised.
"""
import logging

import resend
from django.conf import settings
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY


def send_email_via_resend(to_email, subject, html_body, scheduled_at=None):
    """
    Sends a single transactional email through Resend.

    Args:
        to_email: recipient email address.
        subject: email subject line.
        html_body: rendered HTML content.
        scheduled_at: optional ISO-8601 datetime string (or a Resend
            natural-language string like "in 1 hour") to delay delivery.

    Returns:
        The Resend API response dict, or None if sending failed. Failures
        are logged and swallowed -- email is never allowed to break the
        calling workflow.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY is not set -- skipping email to %s (%s)", to_email, subject)
        return None

    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at

    try:
        response = resend.Emails.send(payload)
        logger.info(
            "Resend email queued: to=%s subject=%s scheduled_at=%s id=%s",
            to_email, subject, scheduled_at, response.get("id") if response else None,
        )
        return response
    except Exception as exc:  # Resend SDK can raise various error types
        logger.error("Resend email failed: to=%s subject=%s error=%s", to_email, subject, exc)
        return None


def notify_user(user, meeting, notification_type, title, message, scheduled_at=None):
    """
    Creates the in-app Notification record and dispatches the matching
    email. The in-app record is created unconditionally; the email send
    is best-effort and never blocks this function from completing.
    """
    Notification.objects.create(
        user=user,
        meeting=meeting,
        title=title,
        message=message,
        notification_type=notification_type,
    )
    send_email_via_resend(
        to_email=user.email,
        subject=title,
        html_body=f"<p>{message}</p>",
        scheduled_at=scheduled_at,
    )


def notify_meeting_created(meeting, recipients):
    """Fires immediately when a meeting moves from DRAFT to OPEN."""
    for user in recipients:
        notify_user(
            user=user,
            meeting=meeting,
            notification_type=Notification.NotificationType.MEETING_CREATED,
            title=f"New meeting: {meeting.title}",
            message=(
                f"A new meeting '{meeting.title}' has been created. "
                f"Please submit your availability before "
                f"{meeting.availability_deadline:%b %d, %Y %H:%M}."
            ),
        )


def notify_meeting_scheduled(meeting, recipients):
    """Fires immediately once an admin confirms a final slot."""
    for user in recipients:
        notify_user(
            user=user,
            meeting=meeting,
            notification_type=Notification.NotificationType.MEETING_SCHEDULED,
            title=f"Meeting scheduled: {meeting.title}",
            message=(
                f"'{meeting.title}' has been scheduled for "
                f"{meeting.final_start_time:%b %d, %Y %H:%M}."
            ),
        )


def notify_meeting_cancelled(meeting, recipients):
    """Fires immediately when a meeting is cancelled."""
    for user in recipients:
        notify_user(
            user=user,
            meeting=meeting,
            notification_type=Notification.NotificationType.MEETING_CANCELLED,
            title=f"Meeting cancelled: {meeting.title}",
            message=f"'{meeting.title}' has been cancelled.",
        )


def schedule_deadline_reminder(meeting, recipients, hours_before=24):
    """
    Schedules a reminder email via Resend's native scheduling, timed to
    land `hours_before` hours ahead of the meeting's availability_deadline.

    This does NOT create an in-app Notification row immediately, since the
    reminder hasn't actually been sent yet -- only the email is scheduled.
    If the computed send time has already passed, the reminder is skipped
    and logged rather than sent immediately (avoids surprising a member
    with a "reminder" the moment they're added to a near-deadline meeting).
    """
    send_at = meeting.availability_deadline - timezone.timedelta(hours=hours_before)
    if send_at <= timezone.now():
        logger.warning(
            "Skipping deadline reminder for meeting=%s: computed send_at already in the past",
            meeting.id,
        )
        return

    scheduled_at_iso = send_at.isoformat()
    for user in recipients:
        send_email_via_resend(
            to_email=user.email,
            subject=f"Reminder: submit your availability for '{meeting.title}'",
            html_body=(
                f"<p>Hi {user.first_name or user.email},</p>"
                f"<p>This is a reminder to submit your availability for "
                f"'{meeting.title}' before "
                f"{meeting.availability_deadline:%b %d, %Y %H:%M}.</p>"
            ),
            scheduled_at=scheduled_at_iso,
        )
