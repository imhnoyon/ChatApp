from unittest.mock import AsyncMock, patch

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Conversation, Message
from .views import MessageEditView, UserListView

User = settings.AUTH_USER_MODEL


class UserListViewTests(TestCase):
	def setUp(self):
		self.factory = APIRequestFactory()
		self.user1 = User.objects.create_user(username='user1', password='pass12345')
		self.user2 = User.objects.create_user(username='user2', password='pass12345')
		self.user3 = User.objects.create_user(username='user3', password='pass12345')

	def test_user_list_excludes_current_user(self):
		request = self.factory.get('/users/')
		force_authenticate(request, user=self.user1)

		response = UserListView.as_view()(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 2)
		usernames = [u['username'] for u in response.data]
		self.assertIn('user2', usernames)
		self.assertIn('user3', usernames)
		self.assertNotIn('user1', usernames)


class MessageEditViewTests(TestCase):
	def setUp(self):
		self.factory = APIRequestFactory()
		self.sender = User.objects.create_user(username='sender', password='pass12345')
		self.other_user = User.objects.create_user(username='other', password='pass12345')
		self.conversation = Conversation.objects.create()
		self.conversation.participants.add(self.sender, self.other_user)
		self.message = Message.objects.create(
			conversation=self.conversation,
			sender=self.sender,
			text='Original message',
			status='delivered',
		)

	@patch('Chats.views.get_channel_layer')
	def test_sender_can_edit_own_message(self, mock_get_channel_layer):
		mock_channel_layer = mock_get_channel_layer.return_value
		mock_channel_layer.group_send = AsyncMock()
		request = self.factory.patch(
			f'/conversations/{self.conversation.id}/messages/{self.message.id}/edit/',
			{'text': 'Updated message'},
			format='json',
		)
		force_authenticate(request, user=self.sender)

		response = MessageEditView.as_view()(request, conv_id=self.conversation.id, message_id=self.message.id)

		self.assertEqual(response.status_code, 200)
		self.message.refresh_from_db()
		self.assertEqual(self.message.text, 'Updated message')
		self.assertIsNotNone(self.message.edited_at)
		mock_channel_layer.group_send.assert_called_once()

	def test_other_participant_cannot_edit_message(self):
		request = self.factory.patch(
			f'/conversations/{self.conversation.id}/messages/{self.message.id}/edit/',
			{'text': 'Updated message'},
			format='json',
		)
		force_authenticate(request, user=self.other_user)

		response = MessageEditView.as_view()(request, conv_id=self.conversation.id, message_id=self.message.id)

		self.assertEqual(response.status_code, 403)
		self.message.refresh_from_db()
		self.assertEqual(self.message.text, 'Original message')
