from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.ConversationListView.as_view()),
    path('conversations/<int:conv_id>/messages/', views.MessageListView.as_view()),
    path('conversations/with/<int:user_id>/', views.ConversationAPIView.as_view()),
    path('conversations/start/<int:user_id>/', views.ConversationAPIView.as_view()),
]