import json
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from .models import Conversation, Message, Reaction

User = settings.AUTH_USER_MODEL

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

        await self.channel_layer.group_send(self.room, {
            'type': 'user_status_event',
            'user_id': self.user.id,
            'status': 'online',
        })

    async def disconnect(self, code):
        if hasattr(self, 'room'):
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
        elif action == 'edit_message':
            await self.handle_edit_message(data)
        elif action == 'typing':
            await self.handle_typing(data)
        elif action == 'seen':
            await self.handle_seen(data)
        elif action == 'mark_read':
            await self.handle_mark_read()
        elif action == 'react':
            await self.handle_react(data)
        elif action == 'presence_ping':
            await self.channel_layer.group_send(self.room, {
                'type': 'presence_query_event',
                'sender_id': self.user.id,
            })
        elif action == 'presence_pong':
            await self.channel_layer.group_send(self.room, {
                'type': 'user_status_event',
                'user_id': self.user.id,
                'status': 'online',
            })

    async def handle_send(self, data):
        text = data.get('text', '').strip()
        if not text: return
        msg = await self.save_message(text)
        await self.broadcast_message(msg, event_type='chat_message')

    async def handle_edit_message(self, data):
        msg_id = data.get('message_id')
        text = data.get('text', '').strip()
        if not msg_id or not text:
            return

        message = await self.db_edit_message(msg_id, text)
        if message is None:
            return

        await self.broadcast_message(message, event_type='message_edited')

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

    async def handle_react(self, data):
        msg_id = data.get('message_id')
        emoji = data.get('emoji')
        if not msg_id or not emoji: return
        
        reaction_data = await self.db_add_reaction(msg_id, emoji)
        if reaction_data is not None:
            await self.channel_layer.group_send(self.room, {
                'type': 'reaction_event',
                'message_id': msg_id,
                'reactions': reaction_data
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
            'created_at': event.get('created_at'),
            'edited_at': event.get('edited_at'),
            'reactions': []
        }))

    async def message_edited(self, event):
        await self.send(json.dumps({
            'type': 'message_edited',
            'id': event.get('id'),
            'text': event.get('text'),
            'sender_id': event.get('sender_id'),
            'sender_name': event.get('sender_name'),
            'status': event.get('status'),
            'created_at': event.get('created_at'),
            'edited_at': event.get('edited_at'),
            'reactions': event.get('reactions', []),
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

    async def reaction_event(self, event):
        await self.send(json.dumps({
            'type': 'reaction',
            'message_id': event.get('message_id'),
            'reactions': event.get('reactions')
        }))

    async def chat_message_media(self, event):
        await self.send(json.dumps({
            'type': 'message',
            **event.get('message')
        }))

    async def user_status_event(self, event):
        await self.send(json.dumps({
            'type': 'status',
            'user_id': event.get('user_id'),
            'status': event.get('status'),
        }))

    async def presence_query_event(self, event):
        if event['sender_id'] != self.user.id:
            await self.send(json.dumps({'type': 'presence_query'}))

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

    async def broadcast_message(self, msg, event_type='chat_message'):
        await self.channel_layer.group_send(self.room, {
            'type': event_type,
            'id': msg.id,
            'text': msg.text,
            'sender_id': msg.sender_id,
            'sender_name': msg.sender.username,
            'status': msg.status,
            'created_at': timezone.localtime(msg.created_at).isoformat(),
            'edited_at': timezone.localtime(msg.edited_at).isoformat() if msg.edited_at else None,
            'reactions': [],
        })

    @database_sync_to_async
    def mark_seen(self, msg_id):
        Message.objects.filter(id=msg_id).exclude(sender=self.user).update(status='seen')

    @database_sync_to_async
    def db_mark_all_seen(self):
        msgs = Message.objects.filter(conversation=self.conversation, status='delivered').exclude(sender=self.user)
        ids = list(msgs.values_list('id', flat=True))
        msgs.update(status='seen')
        return ids

    @database_sync_to_async
    def db_add_reaction(self, msg_id, emoji):
        try:
            msg = Message.objects.get(id=msg_id)
            # Toggle reaction: if same emoji, remove it. If different, update it.
            existing = Reaction.objects.filter(message=msg, user=self.user).first()
            if existing:
                if existing.emoji == emoji:
                    existing.delete()
                else:
                    existing.emoji = emoji
                    existing.save()
            else:
                Reaction.objects.create(message=msg, user=self.user, emoji=emoji)
            
            # Return fresh list of reactions for this message
            res = []
            for r in msg.reactions.all():
                res.append({'emoji': r.emoji, 'user': r.user.id, 'username': r.user.username})
            return res
        except:
            return None

    @database_sync_to_async
    def db_edit_message(self, msg_id, text):
        try:
            msg = Message.objects.select_related('sender').get(id=msg_id, conversation=self.conversation)
            if msg.sender_id != self.user.id:
                return None
            if msg.message_type != 'text':
                return None
            msg.text = text
            msg.edited_at = timezone.now()
            msg.save(update_fields=['text', 'edited_at'])
            msg.refresh_from_db()
            return msg
        except Message.DoesNotExist:
            return None