from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    password2 = serializers.CharField(write_only=True, required=False, allow_blank=True)
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
            'password2',
            'avatar',
        ]
        extra_kwargs = {
            'email': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def validate(self, attrs):
        password2 = attrs.get('password2')
        if password2 and attrs['password'] != password2:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        if attrs.get('email') and User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({'email': 'This email is already in use.'})
        return attrs

    def create(self, validated_data):
        avatar = validated_data.pop('avatar', None)
        validated_data.pop('password2', None)
        user = User.objects.create_user(**validated_data)
        if avatar:
            user.avatar = avatar
            user.save(update_fields=['avatar'])
        return user


class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username_or_email = attrs.get('username', '').strip()
        if username_or_email and '@' in username_or_email:
            user = User.objects.filter(email__iexact=username_or_email).first()
            if user:
                attrs['username'] = user.username
        return super().validate(attrs)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['full_name'] = f"{user.first_name} {user.last_name}".strip()
        return token


class UserProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'avatar', 'bio', 'created_at']
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        avatar = instance.avatar.url if instance.avatar else None
        if avatar and request is not None:
            avatar = request.build_absolute_uri(avatar)
        data['avatar'] = avatar
        return data

    def update(self, instance, validated_data):
        avatar = validated_data.pop('avatar', serializers.empty)
        bio = validated_data.pop('bio', serializers.empty)

        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        
        if avatar is not serializers.empty:
            instance.avatar = avatar
        if bio is not serializers.empty:
            instance.bio = bio
        
        instance.save()
        return instance
