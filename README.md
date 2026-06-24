# OPUS Africa Meeting Scheduling API

Django REST Framework backend for OPUS Africa's meeting scheduling system.
Members vote on admin-proposed time slots; the system scores and ranks
those slots; an admin (e.g. the Secretary) reviews the ranking and
confirms the final time. **The system recommends. It never auto-decides.**

---

## Stack

| Concern | Choice |
|---|---|
| Framework | Django 5.0 + Django REST Framework |
| Auth | JWT via `djangorestframework-simplejwt` (access + refresh, blacklist on logout) |
| API docs | `drf-spectacular` (OpenAPI 3 → Swagger UI + Redoc) |
| Email | [Resend](https://resend.com), including native scheduled sends |
| DB | SQLite locally, PostgreSQL in production (via `DATABASE_URL`) |
| Testing | Postman collection included |

---

## Project layout

```
opus_scheduler/
├── config/                # settings (base/development/production), urls, wsgi/asgi
├── core/                  # shared permissions, pagination, exception handling
├── accounts/              # custom User model (email login), registration, JWT endpoints
├── organizations/         # Organization + Membership (role lives here, not on User)
├── meetings/              # Meeting, MeetingSlot, MeetingAttendance + services.py (the scoring/decision engine)
├── availability/          # Availability (votes) + services.py (cast_vote, eligibility)
├── notifications/         # Notification model + services.py (Resend integration)
└── postman/                # Postman collection + environment
```

Every app with real business logic has a `services.py` — views stay thin
(parse request -- call service -- serialize response). This is where the
scheduling rules live, and it's why `meetings/services.py` can be unit
tested without spinning up the API at all.

---

## Setup

```bash
cd opus_scheduler
python -m venv venv && source venv/bin/activate      # optional but recommended
pip install -r requirements.txt

cp .env.example .env
# edit .env: set SECRET_KEY, RESEND_API_KEY, RESEND_FROM_EMAIL

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is now at `http://localhost:8000/api/v1/`.

- **Swagger UI:** `http://localhost:8000/api/docs/`
- **Redoc:** `http://localhost:8000/api/redoc/`
- **Raw OpenAPI schema:** `http://localhost:8000/api/schema/`
- **Django admin:** `http://localhost:8000/admin/`

---

## Resend (email) setup

1. Create an account at [resend.com](https://resend.com), verify a sending domain (or use their test domain while developing).
2. Grab an API key and put it in `.env` as `RESEND_API_KEY`.
3. Set `RESEND_FROM_EMAIL` to a verified sender, e.g. `OPUS Africa <notifications@yourdomain.org>`.

If `RESEND_API_KEY` is unset, the app **does not crash** — `notifications/services.py`
logs a warning and skips the send. This means you can develop and test
the entire scheduling flow without a Resend account; emails just won't
go out until you add a key.

**Scheduled sends:** when a meeting moves to `OPEN`, a deadline reminder
is scheduled 24 hours before `availability_deadline` using Resend's native
`scheduled_at` parameter (see `schedule_deadline_reminder()` in
`notifications/services.py`) — the email is queued by Resend itself, not
by a Celery task or cron job in this app.

---

## Testing with Postman

Import both files from `postman/`:

- `OPUS_Africa_API.postman_collection.json`
- `OPUS_Africa_Local.postman_environment.json`

Select the **OPUS Africa - Local** environment, then run requests in this
order:

1. **Auth → Register** (or use an existing account)
2. **Auth → Login** — this automatically saves `access_token` /
   `refresh_token` into collection variables. Every other request in the
   collection is pre-configured to send `Authorization: Bearer {{access_token}}`.
3. **Organizations → Create Organization** — saves `organization_id`.
4. **Memberships → Add Member to Organization** — make yourself ADMIN.
5. **Meetings → Create Meeting (DRAFT)** — saves `meeting_id`.
6. **Meeting Slots → Propose Slot 1 / Propose Slot 2** — saves `slot_id` / `slot_id_2`.
7. **Meetings → Open Voting**.
8. **Availability → Cast Vote** (run as different logged-in users to simulate multiple members voting).
9. **Meetings → Get Best Slots** — see the ranked recommendation.
10. **Meetings → Schedule Meeting** — the only call that locks in a final time.

Access tokens expire after 15 minutes; use **Auth → Refresh Token** to get
a new one without logging in again.

---

## The scheduling workflow, in order

```
DRAFT  --[open-voting]-->  OPEN  --[deadline passes or close-voting]-->  CLOSED
                              |
                              v
                    members cast-vote on slots
                              |
                              v
                   GET best-slots  (read-only ranking, recalculated live)
                              |
                              v
                  admin calls POST schedule  -->  SCHEDULED
```

- `GET best-slots` **never writes to the database**. It's safe to call as
  often as you like while voting is in progress.
- `POST schedule` is the **only** endpoint that sets `final_start_time`,
  `final_end_time`, or flips status to `SCHEDULED`. The admin can pick
  *any* slot on the meeting, not just the top-ranked one.
- A slot with a `NOT_AVAILABLE` vote from a required attendee is marked
  `eligible: false` and sorts below eligible slots — but it's still
  visible and still schedulable if the admin chooses to override it.

---

## Scoring rules (`meetings/services.py`)

| Vote | Weight |
|---|---|
| `AVAILABLE` | 1.0 |
| `MAYBE` | 0.5 |
| `NOT_AVAILABLE` | 0.0 |

Ranking order for `calculate_best_slots()`:

1. Eligible slots (pass required-attendee + quorum checks) rank above ineligible ones.
2. Higher weighted score wins.
3. Tie → higher `percentage_available` wins.
4. Tie → earliest `start_time` wins.
5. Still tied → both flagged `manual_decision_required: true` for the admin to break manually.

---

## Key function names (services layer)

| Function | App | Purpose |
|---|---|---|
| `calculate_slot_score` | meetings | Scores a single slot |
| `calculate_best_slots` | meetings | Ranks all slots on a meeting |
| `validate_vote_eligibility` | meetings | Checks if a user may vote right now |
| `open_meeting_voting` | meetings | DRAFT → OPEN, fires notifications |
| `close_meeting_voting` | meetings | OPEN → CLOSED |
| `schedule_meeting` | meetings | **The only function that locks in a final time** |
| `cancel_meeting` | meetings | Cancels at any stage |
| `cast_vote` | availability | Upserts a user's vote on a slot |
| `get_meeting_votes` / `get_user_votes_for_meeting` | availability | Read helpers |
| `send_email_via_resend` | notifications | Low-level Resend call, supports `scheduled_at` |
| `notify_user` | notifications | Creates in-app Notification + dispatches email |
| `notify_meeting_created` / `notify_meeting_scheduled` / `notify_meeting_cancelled` | notifications | Immediate notifications |
| `schedule_deadline_reminder` | notifications | Schedules a future-dated Resend email |

---

## Permissions model

Role lives on `organizations.Membership`, not on the user account:

- **ADMIN** — full control: create/edit meetings, manage memberships, schedule, cancel.
- **EXECUTIVE** — can create/edit meetings and slots, cannot manage memberships.
- **MEMBER** — can read meetings and cast votes.
- **GUEST** — read-only.

`meetings.permissions.IsMeetingOrgAdminOrReadOnly` enforces: any active
org member can read; only ADMIN/EXECUTIVE can write.

---

## Environments

| File | DB | Debug | Notes |
|---|---|---|---|
| `config/settings/development.py` | SQLite | `True` | Console email backend for plain Django mail |
| `config/settings/production.py` | PostgreSQL (`DATABASE_URL`) | `False` | HTTPS redirect, HSTS, secure cookies |

`manage.py` defaults to `development`. Set
`DJANGO_SETTINGS_MODULE=config.settings.production` when deploying.

---

## What's deliberately not included (yet)

- Automated test suite (the architecture is built for it — every rule
  lives in a pure-ish `services.py` function — but tests weren't written
  in this pass).
- Celery/async task queue. Resend's own `scheduled_at` parameter handles
  delayed sends, so there's no background worker to run for that. If you
  later need recurring jobs (e.g. a daily digest), that's where Celery
  or `django-q` would come in.
- AI-assisted features (NL availability parsing, smart suggestions,
  etc.) — intentionally left out per a prior decision to keep this
  release purely rule-based.
