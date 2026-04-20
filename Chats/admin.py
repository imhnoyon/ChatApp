from django.contrib import admin

# Register your models here.
from .models import Conversation, Message

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id','created_at')
    search_fields = ('id',)
    
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'text', 'created_at')
    search_fields = ('conversation__id', 'sender__username', 'text')