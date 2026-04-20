"""
JWT WebSocket Authentication Middleware
Allows WebSocket connections to authenticate using JWT tokens from:
1. Query parameter: ws://host/path?token=<jwt_token>
2. Authorization header (converted from HTTP headers)
"""

from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs


class JWTWebsocketMiddleware(BaseMiddleware):
    """
    JWT Middleware for WebSocket connections.
    Authenticates using JWT token from query parameters or headers.
    """

    async def __call__(self, scope, receive, send):
        """
        Intercept WebSocket connection and authenticate using JWT
        """
        # Only process websocket connections
        if scope['type'] != 'websocket':
            await super().__call__(scope, receive, send)
            return

        # Extract token from query params or headers
        token = self.get_token_from_scope(scope)
        
        if token:
            # Authenticate user using JWT token
            user = await self.authenticate_token(token)
            if user:
                scope['user'] = user
            else:
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()

        await super().__call__(scope, receive, send)

    @staticmethod
    def get_token_from_scope(scope):
        """
        Extract JWT token from:
        1. Query parameter 'token'
        2. Headers 'Authorization'
        """
        # Try query parameters first
        query_string = scope.get('query_string', b'').decode()
        if query_string:
            query_params = parse_qs(query_string)
            if 'token' in query_params:
                return query_params['token'][0]

        # Try Authorization header
        headers = {
            name.decode(): value.decode()
            for name, value in scope.get('headers', [])
        }
        auth_header = headers.get('authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix

        return None

    @staticmethod
    @database_sync_to_async
    def authenticate_token(token):
        """
        Authenticate JWT token and return user object
        """
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated_token)
        except (AuthenticationFailed, InvalidToken, AttributeError, TypeError, Exception):
            return None
