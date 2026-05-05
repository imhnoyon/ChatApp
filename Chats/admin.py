from django.contrib import admin

# Register your models here.
from .models import Call, CallParticipant, Conversation, Message

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id','created_at')
    search_fields = ('id',)
    
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'text', 'created_at')
    search_fields = ('conversation__id', 'sender__username', 'text')
    
    
@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ('id', 'initiator', 'receiver', 'started_at', 'ended_at')
    search_fields = ('initiator__username', 'receiver__username')
    
@admin.register(CallParticipant)
class CallParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'call', 'user', 'status', 'joined_at', 'left_at')
    search_fields = ('call__id', 'user__username')