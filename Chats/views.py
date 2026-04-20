from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = request.user.conversations.all()
        serializer = ConversationSerializer(conversations, many=True, context={'request': request})
        return Response(serializer.data)


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