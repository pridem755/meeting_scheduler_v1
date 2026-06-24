from rest_framework import permissions

from organizations.models import Membership


class IsMeetingOrgAdminOrReadOnly(permissions.BasePermission):
    """
    SAFE methods (GET/HEAD/OPTIONS): any active member of the meeting's
    organization can read.
    Unsafe methods (POST/PUT/PATCH/DELETE): only ADMIN or EXECUTIVE role
    within that organization.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        organization = obj.organization if hasattr(obj, "organization") else obj.meeting.organization
        membership = Membership.objects.filter(
            user=request.user, organization=organization, is_active=True
        ).first()

        if not membership:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return membership.role in (Membership.Role.ADMIN, Membership.Role.EXECUTIVE)
