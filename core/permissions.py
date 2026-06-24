"""
Permission classes shared across apps. App-specific permission rules
(e.g. meeting-scoped admin checks) live in that app's own permissions.py
and typically build on top of these.
"""
from rest_framework import permissions

from organizations.models import Membership


class IsOrgAdmin(permissions.BasePermission):
    """Grants access only to users with an ADMIN membership in the given organization."""

    def has_object_permission(self, request, view, obj):
        organization = getattr(obj, "organization", obj)
        return Membership.objects.filter(
            user=request.user,
            organization=organization,
            role=Membership.Role.ADMIN,
            is_active=True,
        ).exists()


class IsAdminOrReadOnly(permissions.BasePermission):
    """Any active org member can read; only ADMIN role can write."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        organization = getattr(obj, "organization", obj)
        return Membership.objects.filter(
            user=request.user,
            organization=organization,
            role=Membership.Role.ADMIN,
            is_active=True,
        ).exists()


class IsSelfOrOrgAdmin(permissions.BasePermission):
    """Allows a user to act on their own record, or an org admin to act on anyone's."""

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        if owner == request.user:
            return True

        organization = getattr(obj, "organization", None)
        if organization is None and hasattr(obj, "meeting"):
            organization = obj.meeting.organization

        if organization is None:
            return False

        return Membership.objects.filter(
            user=request.user,
            organization=organization,
            role=Membership.Role.ADMIN,
            is_active=True,
        ).exists()
