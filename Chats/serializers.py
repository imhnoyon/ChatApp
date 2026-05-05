from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, Message, Reaction, Call, CallParticipant

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name','avatar']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

class ReactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = Reaction
        fields = ['emoji', 'username', 'user']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    created_at = serializers.SerializerMethodField()
    edited_at = serializers.SerializerMethodField()
    reactions = ReactionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'text', 'status', 'created_at', 'edited_at', 'reactions', 'file', 'message_type']
        
    def get_created_at(self, obj):
        return timezone.localtime(obj.created_at).isoformat()

    def get_edited_at(self, obj):
        return timezone.localtime(obj.edited_at).isoformat() if obj.edited_at else None

class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    def get_other_user(self, obj):
        user = self.context['request'].user
        return UserSerializer(obj.get_other_user(user)).data

    def get_last_message(self, obj):
        last = obj.messages.last()
        return MessageSerializer(last).data if last else None

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.messages.exclude(sender=user).exclude(status='seen').count()

    class Meta:
        model = Conversation
        fields = ['id', 'other_user', 'last_message', 'unread_count', 'created_at']


class CallParticipantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    joined_at = serializers.SerializerMethodField()
    left_at = serializers.SerializerMethodField()

    class Meta:
        model = CallParticipant
        fields = ['id', 'user', 'status', 'joined_at', 'left_at', 'is_audio_enabled', 'is_video_enabled']

    def get_joined_at(self, obj):
        return timezone.localtime(obj.joined_at).isoformat() if obj.joined_at else None

    def get_left_at(self, obj):
        return timezone.localtime(obj.left_at).isoformat() if obj.left_at else None


class CallSerializer(serializers.ModelSerializer):
    initiator = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    participants = CallParticipantSerializer(many=True, read_only=True)
    started_at = serializers.SerializerMethodField()
    answered_at = serializers.SerializerMethodField()
    ended_at = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Call
        fields = [
            'id', 'conversation', 'initiator', 'receiver', 'call_type', 
            'status', 'started_at', 'answered_at', 'ended_at', 'duration_seconds',
            'is_group_call', 'participants'
        ]

    def get_started_at(self, obj):
        return timezone.localtime(obj.started_at).isoformat()

    def get_answered_at(self, obj):
        return timezone.localtime(obj.answered_at).isoformat() if obj.answered_at else None

    def get_ended_at(self, obj):
        return timezone.localtime(obj.ended_at).isoformat() if obj.ended_at else None

    def get_duration_seconds(self, obj):
        return obj.get_duration_in_seconds()


class CallHistorySerializer(serializers.ModelSerializer):
    """Simplified serializer for call history list"""
    initiator = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    started_at = serializers.SerializerMethodField()
    ended_at = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Call
        fields = [
            'id', 'initiator', 'receiver', 'call_type', 
            'status', 'started_at', 'ended_at', 'duration_seconds'
        ]

    def get_started_at(self, obj):
        return timezone.localtime(obj.started_at).isoformat()

    def get_ended_at(self, obj):
        return timezone.localtime(obj.ended_at).isoformat() if obj.ended_at else None

    def get_duration_seconds(self, obj):
        return obj.get_duration_in_seconds()