# ChatApp

A Django-based chat application with REST APIs, JWT authentication, and real-time messaging through Channels/WebSockets.

## Features

- User authentication with JWT
- Conversation list and message history APIs
- Real-time chat over WebSockets
- Image and voice/file uploads
- Reactions, seen status, typing indicator, and presence updates

## Tech Stack

- Django 6
- Django REST Framework
- Channels + Daphne
- SQLite

## Setup

Create a virtual environment, install dependencies, and run migrations:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

## Run the project

Start the development server:

```bash
python manage.py runserver 8003
```

If you are using WebSockets, make sure the ASGI server is running through Daphne/Channels support in Django.

## Media files

Uploaded files are served from `MEDIA_URL = /media/` and stored under `chat_media_data/chat_files/`.

## Notes

- WebSocket route for chat: `/ws/chat/<conv_id>/`
- API routes are exposed under `/api/`