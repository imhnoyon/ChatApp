from django.db import models
from django.conf import settings

class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
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

    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('voice', 'Voice'),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sending')
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        text_preview = (self.text or '')[:30]
        return f"{self.sender.username}: {text_preview}"


class Reaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to {self.message.id}"


class Call(models.Model):
    CALL_TYPE_CHOICES = [
        ('voice', 'Voice Call'),
        ('video', 'Video Call'),
    ]
    
    CALL_STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('ended', 'Ended'),
        ('rejected', 'Rejected'),
        ('missed', 'Missed'),
        ('no_answer', 'No Answer'),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='calls'
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='initiated_calls'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_calls'
    )
    call_type = models.CharField(max_length=10, choices=CALL_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES, default='initiated')
    started_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)  # calculated as ended_at - answered_at
    is_group_call = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-started_at']

    def get_duration_in_seconds(self):
        if self.duration:
            return int(self.duration.total_seconds())
        return 0

    def __str__(self):
        return f"{self.get_call_type_display()} call between {self.initiator.username} and {self.receiver.username}"


class CallParticipant(models.Model):
    """For tracking participants in group calls and individual call endpoints"""
    PARTICIPANT_STATUS_CHOICES = [
        ('invited', 'Invited'),
        ('answered', 'Answered'),
        ('declined', 'Declined'),
        ('left', 'Left'),
    ]
    
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='call_participations')
    status = models.CharField(max_length=20, choices=PARTICIPANT_STATUS_CHOICES, default='invited')
    joined_at = models.DateTimeField(blank=True, null=True)
    left_at = models.DateTimeField(blank=True, null=True)
    is_audio_enabled = models.BooleanField(default=True)
    is_video_enabled = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('call', 'user')

    def __str__(self):
        return f"{self.user.username} in call {self.call.id}"