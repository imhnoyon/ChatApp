# 🚀 ChatApp – Real-Time Django Chat Application

A modern and scalable **real-time chat application** built with Django, REST APIs, and WebSockets. It supports instant messaging, media sharing, and live user interaction.

---

## ✨ Features

* 🔐 JWT Authentication (Login & Register)
* 💬 Real-time messaging using WebSockets
* 🧑‍🤝‍🧑 Conversation & chat history
* 📸 Image upload & sharing
* 🎤 Voice message support
* 👍 Emoji reactions
* 👀 Seen & delivery status
* ⌨️ Typing indicator
* 🟢 Online/offline presence tracking

---

## 🛠️ Tech Stack

* **Backend:** Django, Django REST Framework
* **Realtime:** Channels, Daphne
* **Database:** SQLite (Development)
* **Authentication:** JWT
* **Frontend:** Vanilla JavaScript

---

## 📁 Project Structure

```bash
ChatApplication/
│── apps/
│── chat_media_data/
│── staticfiles/
│── manage.py
│── requirements.txt
│── db.sqlite3 (ignored)
```

---

## ⚙️ Setup Instructions

### 1️⃣ Clone Repository

```bash
git clone https://github.com/your-username/chatapp.git
cd chatapp
```

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Apply Migrations

```bash
python manage.py migrate
```

---

## ▶️ Run the Project

```bash
python manage.py runserver 8003
```

---

## ⚡ WebSocket Endpoint

```
ws://localhost:8003/ws/chat/<conversation_id>/
```

---

## 📂 Media Files

* **URL:** `/media/`
* **Storage:** `chat_media_data/chat_files/`

---

## 🔗 API Endpoints

| Feature       | Endpoint                          |
| ------------- | --------------------------------- |
| Auth          | /api/auth/                        |
| Conversations | /api/conversations/               |
| Messages      | /api/conversations/<id>/messages/ |
| Upload        | /api/conversations/<id>/upload/   |

---

## 🧠 How It Works

* REST APIs handle authentication & data
* WebSockets handle real-time messaging
* Messages sync instantly between users
* Media files are uploaded via API and displayed in chat

---

## 🚧 Future Improvements

* PostgreSQL integration
* Redis for Channels
* Push notifications
* Group chat support
* Enhanced security & encryption

---

## 📌 Notes

* Microphone permission required for voice messages
* Use HTTPS or localhost for recording features
* SQLite is recommended only for development

---

## 👨‍💻 Author

**Mahedi Hasan Noyon**
