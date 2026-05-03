from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.UserListView.as_view()),
    path('conversations/', views.ConversationListView.as_view()),
    path('conversations/<int:conv_id>/messages/', views.MessageListView.as_view()),
    path('conversations/with/<int:user_id>/', views.ConversationAPIView.as_view()),
    path('conversations/start/<int:user_id>/', views.ConversationAPIView.as_view()),
    path('conversations/<int:conv_id>/upload/', views.FileUploadView.as_view()),
    path('conversations/<int:conv_id>/messages/<int:message_id>/edit/', views.MessageEditView.as_view()),
]