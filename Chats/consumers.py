import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Conversation, Message

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conv_id = self.scope['url_route']['kwargs']['conv_id']
        self.room = f'chat_{self.conv_id}'
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.conversation = await self.get_conversation()
        if not self.conversation:
            await self.close()
            return

        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

        # Broadcast online status
        await self.channel_layer.group_send(self.room, {
            'type': 'user_status_event',
            'user_id': self.user.id,
            'status': 'online',
        })

    async def disconnect(self, code):
        if hasattr(self, 'room'):
            # Broadcast offline status
            await self.channel_layer.group_send(self.room, {
                'type': 'user_status_event',
                'user_id': self.user.id,
                'status': 'offline',
            })
            await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except:
            return

        action = data.get('action')

        if action == 'send_message':
            await self.handle_send(data)
        elif action == 'typing':
            await self.handle_typing(data)
        elif action == 'seen':
            await self.handle_seen(data)
        elif action == 'mark_read':
            await self.handle_mark_read()

    # ── Handlers ───────────────────────────────────

    async def handle_send(self, data):
        text = data.get('text', '').strip()
        if not text: return
        msg = await self.save_message(text)
        await self.channel_layer.group_send(self.room, {
            'type': 'chat_message',
            'id': msg.id,
            'text': msg.text,
            'sender_id': self.user.id,
            'sender_name': self.user.username,
            'status': 'delivered',
            'time': msg.created_at.strftime('%H:%M'),
        })

    async def handle_typing(self, data):
        await self.channel_layer.group_send(self.room, {
            'type': 'typing_event',
            'sender_id': self.user.id,
            'is_typing': data.get('is_typing', False),
        })

    async def handle_seen(self, data):
        msg_id = data.get('message_id')
        if not msg_id: return
        await self.mark_seen(msg_id)
        await self.channel_layer.group_send(self.room, {
            'type': 'seen_event',
            'message_id': msg_id,
            'seen_by': self.user.id,
        })

    async def handle_mark_read(self):
        mids = await self.db_mark_all_seen()
        for mid in mids:
            await self.channel_layer.group_send(self.room, {
                'type': 'seen_event',
                'message_id': mid,
                'seen_by': self.user.id,
            })

    # ── Broadcast Receivers ────────────────────────

    async def chat_message(self, event):
        await self.send(json.dumps({
            'type': 'message',
            'id': event.get('id'),
            'text': event.get('text'),
            'sender_id': event.get('sender_id'),
            'sender_name': event.get('sender_name'),
            'status': event.get('status'),
            'time': event.get('time'),
        }))

    async def typing_event(self, event):
        if event['sender_id'] != self.user.id:
            await self.send(json.dumps({
                'type': 'typing',
                'sender_id': event.get('sender_id'),
                'is_typing': event.get('is_typing', False),
            }))

    async def seen_event(self, event):
        await self.send(json.dumps({
            'type': 'seen',
            'message_id': event.get('message_id'),
            'seen_by': event.get('seen_by'),
        }))

    async def user_status_event(self, event):
        await self.send(json.dumps({
            'type': 'status',
            'user_id': event.get('user_id'),
            'status': event.get('status'),
        }))

    # ── DB Helpers ─────────────────────────────────

    @database_sync_to_async
    def get_conversation(self):
        return Conversation.objects.filter(id=self.conv_id).first()

    @database_sync_to_async
    def save_message(self, text):
        return Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            text=text,
            status='delivered'
        )

    @database_sync_to_async
    def mark_seen(self, msg_id):
        Message.objects.filter(id=msg_id).exclude(sender=self.user).update(status='seen')

    @database_sync_to_async
    def db_mark_all_seen(self):
        msgs = Message.objects.filter(
            conversation=self.conversation, 
            status='delivered'
        ).exclude(sender=self.user)
        ids = list(msgs.values_list('id', flat=True))
        msgs.update(status='seen')
        return ids