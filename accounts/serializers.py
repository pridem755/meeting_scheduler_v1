from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Read/update shape for a user's own profile."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone_number", "is_active", "date_joined"]
        read_only_fields = ["id", "email", "is_active", "date_joined"]


class RegisterUserSerializer(serializers.ModelSerializer):
    """Input shape for account registration. Hashes the password on create."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "password", "first_name", "last_name", "phone_number"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
