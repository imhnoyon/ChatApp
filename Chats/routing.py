from django.urls import re_path
from . import consumers
from . import call_consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<conv_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/call/(?P<call_id>\d+)/$', call_consumers.CallSignalingConsumer.as_asgi()),
]
