from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import Membership, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "description", "member_count", "created_at", "updated_at"]
        read_only_fields = ["id", "member_count", "created_at", "updated_at"]

    def get_member_count(self, organization) -> int:
        return organization.memberships.filter(is_active=True).count()


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=Membership._meta.get_field("user").related_model.objects.all(),
        source="user",
        write_only=True,
    )

    class Meta:
        model = Membership
        fields = ["id", "user", "user_id", "organization", "role", "position", "is_active", "joined_at"]
        read_only_fields = ["id", "joined_at"]
