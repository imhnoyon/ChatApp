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
    path('conversations/<int:conv_id>/messages/<int:message_id>/delete/', views.MessageDeleteView.as_view()),
    
    # Call endpoints
    path('conversations/<int:conv_id>/calls/initiate/', views.CallInitiateView.as_view()),
    path('conversations/<int:conv_id>/calls/<int:call_id>/answer/', views.CallAnswerView.as_view()),
    path('conversations/<int:conv_id>/calls/<int:call_id>/reject/', views.CallRejectView.as_view()),
    path('conversations/<int:conv_id>/calls/<int:call_id>/end/', views.CallEndView.as_view()),
    path('conversations/<int:conv_id>/calls/<int:call_id>/miss/', views.CallMissView.as_view()),
    path('conversations/<int:conv_id>/calls/history/', views.CallHistoryView.as_view()),
    path('calls/history/', views.UserCallHistoryView.as_view()),
]