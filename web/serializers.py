from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.authtoken.models import Token


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = authenticate(**data)
        if user:
            token, _ = Token.objects.get_or_create(user=user)
            return token  # Token 객체 반환
        raise serializers.ValidationError({
            "error": "Unable to log in with provided credentials."
        })
