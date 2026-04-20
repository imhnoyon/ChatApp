from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.RegisterAPIView.as_view()),
    path('auth/login/',    views.LoginAPIView.as_view()),
    path('auth/logout/',   views.LogoutAPIView.as_view()),
    path('auth/refresh/',  TokenRefreshView.as_view()),   

    # Profile
    path('auth/me/',              views.MeView.as_view()),
    path('auth/change-password/', views.ChangePasswordView.as_view()),
    
    # Users
    path('users/', views.UsersListView.as_view()),

]