from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Conversation

User = get_user_model()


@receiver(post_delete, sender=User)
def delete_user_conversations(sender, instance, **kwargs):
    """
    When a user is deleted, delete all conversations where they are a participant.
    """
    # Get all conversations where this user was a participant
    conversations = Conversation.objects.filter(participants=instance)
    conversations.delete()
