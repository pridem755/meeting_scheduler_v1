from rest_framework.routers import DefaultRouter

from .views import MeetingAttendanceViewSet, MeetingSlotViewSet, MeetingViewSet

router = DefaultRouter()
router.register("meetings", MeetingViewSet, basename="meeting")
router.register("meeting-slots", MeetingSlotViewSet, basename="meeting-slot")
router.register("meeting-attendance", MeetingAttendanceViewSet, basename="meeting-attendance")

urlpatterns = router.urls
