from django.db import models
from django.contrib.auth.models import User

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    def get_other_user(self, user):
        return self.participants.exclude(id=user.id).first()

    def __str__(self):
        return f"Conversation {self.id}"


class Message(models.Model):
    STATUS_CHOICES = [
        ('sending', 'Sending'),
        ('delivered', 'Delivered'),
        ('seen', 'Seen'),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.text[:30]}"