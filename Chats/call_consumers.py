"""
WebRTC Call Signaling Consumer
Handles WebRTC peer-to-peer signaling (offer, answer, ICE candidates)
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from .models import Call

User = settings.AUTH_USER_MODEL


class CallSignalingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for WebRTC signaling during calls.
    Each user joins a call-specific room for peer-to-peer communication.
    """

    async def connect(self):
        self.call_id = self.scope['url_route']['kwargs']['call_id']
        self.user = self.scope['user']
        self.room = f'call_{self.call_id}'

        if not self.user.is_authenticated:
            await self.close()
            return

        # Verify user is part of this call
        call = await self.get_call()
        if not call:
            await self.close()
            return

        if self.user.id not in [call.initiator_id, call.receiver_id]:
            await self.close()
            return

        # Add user to the call room
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

        # Notify other participant that this user is connected
        await self.channel_layer.group_send(self.room, {
            'type': 'user_connected',
            'user_id': self.user.id,
        })

    async def disconnect(self, code):
        if hasattr(self, 'room'):
            # Notify other participant that this user is disconnected
            await self.channel_layer.group_send(self.room, {
                'type': 'user_disconnected',
                'user_id': self.user.id,
            })
            await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except:
            return

        action = data.get('action')

        if action == 'webrtc_offer':
            await self.handle_webrtc_offer(data)
        elif action == 'webrtc_answer':
            await self.handle_webrtc_answer(data)
        elif action == 'webrtc_ice_candidate':
            await self.handle_webrtc_ice_candidate(data)
        elif action == 'call_stats':
            await self.handle_call_stats(data)

    async def handle_webrtc_offer(self, data):
        """Forward WebRTC offer to the other peer"""
        offer = data.get('offer')
        if not offer:
            return

        await self.channel_layer.group_send(self.room, {
            'type': 'webrtc_offer_message',
            'offer': offer,
            'from_user_id': self.user.id,
        })

    async def handle_webrtc_answer(self, data):
        """Forward WebRTC answer to the other peer"""
        answer = data.get('answer')
        if not answer:
            return

        await self.channel_layer.group_send(self.room, {
            'type': 'webrtc_answer_message',
            'answer': answer,
            'from_user_id': self.user.id,
        })

    async def handle_webrtc_ice_candidate(self, data):
        """Forward ICE candidate to the other peer"""
        candidate = data.get('candidate')
        if not candidate:
            return

        await self.channel_layer.group_send(self.room, {
            'type': 'webrtc_ice_candidate_message',
            'candidate': candidate,
            'from_user_id': self.user.id,
        })

    async def handle_call_stats(self, data):
        """Receive and store call statistics"""
        stats = data.get('stats')
        if not stats:
            return

        # Store call statistics (can be extended to save to DB)
        await self.channel_layer.group_send(self.room, {
            'type': 'call_stats_message',
            'stats': stats,
            'from_user_id': self.user.id,
        })

    # ── Broadcast Receivers ─────────────────────────

    async def user_connected(self, event):
        """Notify user that other participant is connected"""
        if event['user_id'] != self.user.id:
            await self.send(json.dumps({
                'type': 'user_connected',
                'user_id': event['user_id'],
            }))

    async def user_disconnected(self, event):
        """Notify user that other participant is disconnected"""
        await self.send(json.dumps({
            'type': 'user_disconnected',
            'user_id': event['user_id'],
        }))

    async def webrtc_offer_message(self, event):
        """Forward WebRTC offer to receiver"""
        if event['from_user_id'] != self.user.id:
            await self.send(json.dumps({
                'type': 'webrtc_offer',
                'offer': event.get('offer'),
                'from_user_id': event['from_user_id'],
            }))

    async def webrtc_answer_message(self, event):
        """Forward WebRTC answer to initiator"""
        if event['from_user_id'] != self.user.id:
            await self.send(json.dumps({
                'type': 'webrtc_answer',
                'answer': event.get('answer'),
                'from_user_id': event['from_user_id'],
            }))

    async def webrtc_ice_candidate_message(self, event):
        """Forward ICE candidate to other peer"""
        if event['from_user_id'] != self.user.id:
            await self.send(json.dumps({
                'type': 'webrtc_ice_candidate',
                'candidate': event.get('candidate'),
                'from_user_id': event['from_user_id'],
            }))

    async def call_stats_message(self, event):
        """Forward call statistics to other peer"""
        await self.send(json.dumps({
            'type': 'call_stats',
            'stats': event.get('stats'),
            'from_user_id': event['from_user_id'],
        }))

    # ── DB Helpers ──────────────────────────────────

    @database_sync_to_async
    def get_call(self):
        """Fetch call from database"""
        try:
            return Call.objects.get(id=self.call_id)
        except Call.DoesNotExist:
            return None
