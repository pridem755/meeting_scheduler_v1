from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# In development, never actually hit Resend unless you set RESEND_API_KEY --
# Django's console backend is used for plain Django emails (admin, password
# reset, etc.); Resend calls from notifications/services.py still fire if
# you've set a real key in .env, so you can test scheduling end-to-end.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
