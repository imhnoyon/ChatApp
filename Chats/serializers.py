from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Conversation, Message, Reaction

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

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