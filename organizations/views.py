from rest_framework import permissions, viewsets

from core.permissions import IsAdminOrReadOnly

from .models import Membership, Organization
from .serializers import MembershipSerializer, OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD for organizations. Reading is open to any authenticated user; writing is ADMIN-only."""
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]


class MembershipViewSet(viewsets.ModelViewSet):
    """
    Manages who belongs to an organization and what role they hold.
    Filterable by ?organization=<uuid>.
    """
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Membership.objects.select_related("user", "organization")
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        return queryset
