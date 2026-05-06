from django.db.models import Q
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Conversation, Message, Call, CallParticipant
from .serializers import ConversationSerializer, MessageSerializer, UserSerializer, CallSerializer, CallHistorySerializer
from rest_framework.parsers import MultiPartParser, FormParser
import mimetypes
from pathlib import Path
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

User = get_user_model()


def format_call_for_websocket(call):
    """Format call object for WebSocket in Flutter-compatible format"""
    return {
        "id": call.id,
        "conversation": call.conversation_id,
        "caller": {
            "id": call.initiator.id,
            "username": call.initiator.username
        },
        "receiver": {
            "id": call.receiver.id,
            "username": call.receiver.username
        },
        "call_type": call.call_type,
        "status": call.status,
        "start_time": call.answered_at.isoformat() if call.answered_at else None,
        "end_time": call.ended_at.isoformat() if call.ended_at else None
    }


class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.exclude(id=request.user.id).exclude(is_staff=True)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = request.user.conversations.all()
        serializer = ConversationSerializer(conversations, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        """
        Start a new conversation with a user by user_id in POST body.
        Example: POST /conversations/ {"user_id": 2}
        """
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user1 = request.user
            user2 = User.objects.get(id=user_id)

            # Find if a conversation already exists between the two users
            conversation = Conversation.objects.filter(
                participants=user1
            ).filter(
                participants=user2
            ).first()

            if not conversation:
                conversation = Conversation.objects.create()
                conversation.participants.add(user1, user2)

            serializer = ConversationSerializer(conversation, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conv_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            # Check if the user is a participant
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)
            
            messages = conversation.messages.all()
            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)


class ConversationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        try:
            user1 = request.user
            user2 = User.objects.get(id=user_id)

            # Find if a conversation already exists between the two users
            conversation = Conversation.objects.filter(
                participants=user1
            ).filter(
                participants=user2
            ).first()

            if not conversation:
                # If not, create a new one
                conversation = Conversation.objects.create()
                conversation.participants.add(user1, user2)

            serializer = ConversationSerializer(conversation, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, conv_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)
            
            msg_type = request.data.get('message_type', 'image')
            file_obj = request.FILES.get('file')
  
            
            if not file_obj:
                return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

            # Ensure file extension matches the uploaded content-type so browsers can play it
            try:
                ct = getattr(file_obj, 'content_type', '') or ''
                ct_main = ct.split(';')[0].strip()
                ext = None
                if 'webm' in ct_main:
                    ext = '.webm'
                elif 'ogg' in ct_main or 'oga' in ct_main:
                    ext = '.ogg'
                else:
                    ext = mimetypes.guess_extension(ct_main) or ''

                if ext:
                    file_obj.name = Path(file_obj.name).stem + ext
            except Exception:
                pass

            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                message_type=msg_type,
                file=file_obj,
                status='delivered'
            )

            serializer = MessageSerializer(msg, context={'request': request})
            data = serializer.data
            
            # Broadcast to the room via Channel Layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'chat_message_media',
                    'message': data
                }
            )

            return Response(data, status=status.HTTP_201_CREATED)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MessageEditView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, conv_id, message_id):
        return self._edit_message(request, conv_id, message_id)

    def post(self, request, conv_id, message_id):
        return self._edit_message(request, conv_id, message_id)

    def _edit_message(self, request, conv_id, message_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            message = Message.objects.select_related('sender').filter(id=message_id, conversation=conversation).first()
            if not message:
                return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

            if message.sender_id != request.user.id:
                return Response({'error': 'You can only edit your own messages.'}, status=status.HTTP_403_FORBIDDEN)

            if message.message_type != 'text':
                return Response({'error': 'Only text messages can be edited.'}, status=status.HTTP_400_BAD_REQUEST)

            text = (request.data.get('text') or '').strip()
            if not text:
                return Response({'error': 'Text is required.'}, status=status.HTTP_400_BAD_REQUEST)

            message.text = text
            message.edited_at = timezone.now()
            message.save(update_fields=['text', 'edited_at'])

            serializer = MessageSerializer(message, context={'request': request})
            data = serializer.data

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'message_edited',
                    **data,
                }
            )

            return Response(data, status=status.HTTP_200_OK)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MessageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, conv_id, message_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            message = Message.objects.select_related('sender').filter(id=message_id, conversation=conversation).first()
            if not message:
                return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

            if message.sender_id != request.user.id:
                return Response({'error': 'You can only delete your own messages.'}, status=status.HTTP_403_FORBIDDEN)

            # Delete the message file if it exists
            if message.file:
                try:
                    message.file.delete()
                except Exception:
                    pass

            message.delete()

            # Send WebSocket notification about message deletion
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                }
            )

            return Response({'success': 'Message deleted successfully.'}, status=status.HTTP_200_OK)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CallInitiateView(APIView):
    """Initiate a new voice or video call"""
    permission_classes = [IsAuthenticated]

    def post(self, request, conv_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            call_type = request.data.get('call_type', 'voice')
            if call_type not in ['voice', 'video']:
                return Response({'error': 'Invalid call type'}, status=status.HTTP_400_BAD_REQUEST)

            # Get the other participant
            receiver = conversation.get_other_user(request.user)
            if not receiver:
                return Response({'error': 'No other participant in conversation'}, status=status.HTTP_400_BAD_REQUEST)

            # Create a new call
            call = Call.objects.create(
                conversation=conversation,
                initiator=request.user,
                receiver=receiver,
                call_type=call_type,
                status='initiated'
            )

            # Broadcast call initiation via WebSocket
            channel_layer = get_channel_layer()
            call_data = format_call_for_websocket(call)
            
            # Send to conversation group (for users in that conversation)
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'call_initiated',
                    'call': call_data
                }
            )
            
            # ALSO send to receiver's personal notification channel (so they get call even if not in conversation)
            async_to_sync(channel_layer.group_send)(
                f'notifications_{receiver.id}',
                {
                    'type': 'call_initiated',
                    'call': call_data
                }
            )

            return Response(CallSerializer(call, context={'request': request}).data, status=status.HTTP_201_CREATED)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CallAnswerView(APIView):
    """Answer an incoming call"""
    permission_classes = [IsAuthenticated]

    def post(self, request, conv_id, call_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            call = Call.objects.get(id=call_id, conversation=conversation)
            if call.receiver_id != request.user.id:
                return Response({'error': 'Only the receiver can answer this call'}, status=status.HTTP_403_FORBIDDEN)

            if call.status not in ['initiated', 'ringing']:
                return Response({'error': f'Cannot answer call with status {call.status}'}, status=status.HTTP_400_BAD_REQUEST)

            call.status = 'answered'
            call.answered_at = timezone.now()
            call.save()

            # Broadcast call answer via WebSocket
            channel_layer = get_channel_layer()
            call_data = format_call_for_websocket(call)
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'call_answered',
                    'call': call_data
                }
            )

            return Response(CallSerializer(call, context={'request': request}).data, status=status.HTTP_200_OK)
        except Call.DoesNotExist:
            return Response({'error': 'Call not found'}, status=status.HTTP_404_NOT_FOUND)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CallRejectView(APIView):
    """Reject an incoming call"""
    permission_classes = [IsAuthenticated]

    def post(self, request, conv_id, call_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            call = Call.objects.get(id=call_id, conversation=conversation)
            if call.receiver_id != request.user.id:
                return Response({'error': 'Only the receiver can reject this call'}, status=status.HTTP_403_FORBIDDEN)

            if call.status not in ['initiated', 'ringing']:
                return Response({'error': f'Cannot reject call with status {call.status}'}, status=status.HTTP_400_BAD_REQUEST)

            call.status = 'rejected'
            call.ended_at = timezone.now()
            call.save()

            # Broadcast call rejection via WebSocket
            channel_layer = get_channel_layer()
            call_data = format_call_for_websocket(call)
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'call_rejected',
                    'call': call_data
                }
            )

            return Response(CallSerializer(call, context={'request': request}).data, status=status.HTTP_200_OK)
        except Call.DoesNotExist:
            return Response({'error': 'Call not found'}, status=status.HTTP_404_NOT_FOUND)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CallEndView(APIView):
    """End an ongoing call"""
    permission_classes = [IsAuthenticated]

    def post(self, request, conv_id, call_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            call = Call.objects.get(id=call_id, conversation=conversation)
            if call.status != 'answered':
                return Response({'error': f'Cannot end call with status {call.status}'}, status=status.HTTP_400_BAD_REQUEST)

            call.status = 'ended'
            call.ended_at = timezone.now()
            
            # Calculate duration if answered
            if call.answered_at:
                call.duration = call.ended_at - call.answered_at
            
            call.save()

            # Broadcast call end via WebSocket
            channel_layer = get_channel_layer()
            call_data = format_call_for_websocket(call)
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'call_ended',
                    'call': call_data
                }
            )

            return Response(CallSerializer(call, context={'request': request}).data, status=status.HTTP_200_OK)
        except Call.DoesNotExist:
            return Response({'error': 'Call not found'}, status=status.HTTP_404_NOT_FOUND)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CallMissView(APIView):
    """Mark a call as missed (no answer timeout)"""
    permission_classes = [IsAuthenticated]

    def post(self, request, conv_id, call_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            call = Call.objects.get(id=call_id, conversation=conversation)
            if call.status not in ['initiated', 'ringing']:
                return Response({'error': f'Cannot mark call as missed with status {call.status}'}, status=status.HTTP_400_BAD_REQUEST)

            call.status = 'missed'
            call.ended_at = timezone.now()
            call.save()

            # Broadcast call missed via WebSocket
            channel_layer = get_channel_layer()
            call_data = format_call_for_websocket(call)
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'call_missed',
                    'call': call_data
                }
            )

            return Response(CallSerializer(call, context={'request': request}).data, status=status.HTTP_200_OK)
        except Call.DoesNotExist:
            return Response({'error': 'Call not found'}, status=status.HTTP_404_NOT_FOUND)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CallHistoryView(APIView):
    """Get call history for a conversation or user"""
    permission_classes = [IsAuthenticated]

    def get(self, request, conv_id):
        try:
            conversation = Conversation.objects.get(id=conv_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

            calls = Call.objects.filter(conversation=conversation).order_by('-started_at')
            serializer = CallHistorySerializer(calls, many=True)
            return Response(serializer.data)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserCallHistoryView(APIView):
    """Get user's recent calls across all conversations"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get calls where user is initiator or receiver
            calls = Call.objects.filter(
                Q(initiator=request.user) | Q(receiver=request.user)
            ).order_by('-started_at')[:50]  # Limit to 50 recent calls
            
            serializer = CallHistorySerializer(calls, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)