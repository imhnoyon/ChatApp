from django.apps import AppConfig


class ChatsConfig(AppConfig):
    name = 'Chats'

    def ready(self):
        import Chats.signals
