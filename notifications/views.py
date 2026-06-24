from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Lists the authenticated user's own notifications and allows marking them read."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Notification.objects.all()  # used for schema/pk-type introspection; see get_queryset for the real filter

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["patch"], url_path="read")
    def mark_as_read(self, request, pk=None):
        """Marks a single notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_as_read(self, request):
        """Marks every unread notification belonging to the authenticated user as read."""
        updated_count = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"marked_read": updated_count})
