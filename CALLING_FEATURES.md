# Voice & Video Calling Feature Documentation

## Overview
Complete real-time voice and video calling implementation with WebRTC peer-to-peer communication, WebSocket signaling, and call history tracking.

## Database Models

### Call Model
Tracks voice/video calls between users.

```python
class Call(models.Model):
    CALL_TYPES: 'voice', 'video'
    CALL_STATUSES: 'initiated', 'ringing', 'answered', 'ended', 'rejected', 'missed', 'no_answer'
    
    Fields:
    - conversation: ForeignKey to Conversation
    - initiator: User who initiated the call
    - receiver: User receiving the call
    - call_type: 'voice' or 'video'
    - status: Current call status
    - started_at: Timestamp when call was initiated
    - answered_at: Timestamp when call was answered
    - ended_at: Timestamp when call ended
    - duration: DurationField (auto-calculated as ended_at - answered_at)
    - is_group_call: Boolean for future group calling support
```

### CallParticipant Model
Tracks individual participant status in calls (supports future group calls).

```python
class CallParticipant(models.Model):
    Fields:
    - call: ForeignKey to Call
    - user: ForeignKey to User
    - status: 'invited', 'answered', 'declined', 'left'
    - joined_at: When participant joined
    - left_at: When participant left
    - is_audio_enabled: Audio control state
    - is_video_enabled: Video control state
```

## REST API Endpoints

### Initiate a Call
```
POST /api/conversations/<conv_id>/calls/initiate/
Body: {
    "call_type": "voice" | "video"
}
Response: Call object with status='initiated'
```

### Answer a Call
```
POST /api/conversations/<conv_id>/calls/<call_id>/answer/
Response: Call object with status='answered'
```

### Reject a Call
```
POST /api/conversations/<conv_id>/calls/<call_id>/reject/
Response: Call object with status='rejected'
```

### End a Call
```
POST /api/conversations/<conv_id>/calls/<call_id>/end/
Response: Call object with status='ended' and duration calculated
```

### Mark Call as Missed
```
POST /api/conversations/<conv_id>/calls/<call_id>/miss/
Response: Call object with status='missed'
```

### Get Call History (Conversation)
```
GET /api/conversations/<conv_id>/calls/history/
Response: Array of Call objects ordered by date
```

### Get User Call History
```
GET /api/calls/history/
Response: Array of last 50 calls (user is initiator or receiver)
```

## WebSocket Events

### Chat Consumer (ws/chat/<conv_id>/)
Used for in-conversation call signaling:

#### Client → Server Actions
```javascript
// Notify call is ringing
{
    "action": "call_ringing",
    "call_id": 123
}

// Send WebRTC offer
{
    "action": "webrtc_offer",
    "call_id": 123,
    "offer": { /* SDP offer object */ }
}

// Send WebRTC answer
{
    "action": "webrtc_answer",
    "call_id": 123,
    "answer": { /* SDP answer object */ }
}

// Send ICE candidate
{
    "action": "webrtc_ice_candidate",
    "call_id": 123,
    "candidate": { /* ICE candidate object */ }
}
```

#### Server → Client Events
```javascript
// Incoming call notification
{
    "type": "call_initiated",
    "call_data": { /* Call object */ }
}

// Call was answered
{
    "type": "call_answered",
    "call_data": { /* Call object */ }
}

// Call was rejected
{
    "type": "call_rejected",
    "call_data": { /* Call object */ }
}

// Call ended
{
    "type": "call_ended",
    "call_data": { /* Call object with duration */ }
}

// Call missed
{
    "type": "call_missed",
    "call_data": { /* Call object */ }
}

// Call ringing notification
{
    "type": "call_ringing",
    "call_id": 123,
    "initiator_id": 1
}

// WebRTC offer received
{
    "type": "webrtc_offer",
    "call_id": 123,
    "offer": { /* SDP offer object */ },
    "from_user_id": 2
}

// WebRTC answer received
{
    "type": "webrtc_answer",
    "call_id": 123,
    "answer": { /* SDP answer object */ },
    "from_user_id": 2
}

// ICE candidate received
{
    "type": "webrtc_ice_candidate",
    "call_id": 123,
    "candidate": { /* ICE candidate object */ },
    "from_user_id": 2
}
```

### Call Signaling Consumer (ws/call/<call_id>/)
Dedicated WebSocket for peer-to-peer WebRTC signaling:

#### Client → Server Actions
```javascript
{
    "action": "webrtc_offer",
    "offer": { /* SDP offer */ }
}

{
    "action": "webrtc_answer",
    "answer": { /* SDP answer */ }
}

{
    "action": "webrtc_ice_candidate",
    "candidate": { /* ICE candidate */ }
}

{
    "action": "call_stats",
    "stats": { /* Call statistics */ }
}
```

#### Server → Client Events
```javascript
{
    "type": "user_connected",
    "user_id": 2
}

{
    "type": "user_disconnected",
    "user_id": 2
}

{
    "type": "webrtc_offer",
    "offer": { /* SDP offer */ },
    "from_user_id": 2
}

{
    "type": "webrtc_answer",
    "answer": { /* SDP answer */ },
    "from_user_id": 2
}

{
    "type": "webrtc_ice_candidate",
    "candidate": { /* ICE candidate */ },
    "from_user_id": 2
}

{
    "type": "call_stats",
    "stats": { /* Call statistics */ },
    "from_user_id": 2
}
```

## Call Flow

### Initiating a Call

1. **Initiator initiates**: Call `POST /api/conversations/<conv_id>/calls/initiate/` with `call_type`
   - Creates `Call` object with status='initiated'
   - Broadcasts `call_initiated` event to conversation WebSocket room

2. **Receiver receives notification**: `call_initiated` event received via WebSocket

3. **Call starts ringing**: Initiator sends `call_ringing` action via WebSocket
   - Status changes to 'ringing'
   - Receiver gets `call_ringing` notification

4. **Receiver answers**: Call `POST /api/conversations/<conv_id>/calls/<call_id>/answer/`
   - Status changes to 'answered'
   - `answered_at` timestamp recorded
   - Broadcasts `call_answered` event

5. **WebRTC Handshake**:
   - Initiator connects to `ws/call/<call_id>/`
   - Receiver connects to `ws/call/<call_id>/`
   - Initiator sends WebRTC `offer`
   - Receiver sends WebRTC `answer`
   - Both exchange ICE candidates

6. **Call Active**: Media streams flow between peers

7. **Call ends**: Either party calls `POST /api/conversations/<conv_id>/calls/<call_id>/end/`
   - Status changes to 'ended'
   - Duration calculated and stored
   - Broadcasts `call_ended` event
   - Both disconnect from signaling WebSocket

### Rejecting a Call

1. Receiver calls `POST /api/conversations/<conv_id>/calls/<call_id>/reject/`
2. Status changes to 'rejected'
3. Broadcasts `call_rejected` event

### Missed/No Answer

1. If initiator marks as missed: `POST /api/conversations/<conv_id>/calls/<call_id>/miss/`
2. Status changes to 'missed'
3. Broadcasts `call_missed` event

## Serializers

### CallSerializer
Full call details with participants:
```python
Fields: id, conversation, initiator, receiver, call_type, status, 
         started_at, answered_at, ended_at, duration_seconds, 
         is_group_call, participants
```

### CallParticipantSerializer
Individual participant info:
```python
Fields: id, user, status, joined_at, left_at, is_audio_enabled, is_video_enabled
```

### CallHistorySerializer
Simplified call history:
```python
Fields: id, initiator, receiver, call_type, status, started_at, ended_at, duration_seconds
```

## Frontend Implementation Guide

### Required Libraries
- WebRTC API (built-in browser support)
- PeerConnection for audio/video streaming

### JavaScript Setup Example
```javascript
// 1. Initiate call via REST
const response = await fetch(`/api/conversations/${convId}/calls/initiate/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ call_type: 'video' })
});
const call = await response.json();

// 2. Connect to chat WebSocket for signaling
const chatWS = new WebSocket(`ws://.../ws/chat/${convId}/`);
chatWS.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'call_initiated') {
        // Show incoming call UI
    }
};

// 3. When call is answered, connect to call signaling WebSocket
const callWS = new WebSocket(`ws://.../ws/call/${callId}/`);

// 4. Create RTCPeerConnection
const peerConnection = new RTCPeerConnection();

// 5. Add local stream
const stream = await navigator.mediaDevices.getUserMedia({ 
    audio: true, 
    video: true 
});
stream.getTracks().forEach(track => peerConnection.addTrack(track, stream));

// 6. Handle offer/answer through WebSocket
peerConnection.onicecandidate = (event) => {
    if (event.candidate) {
        callWS.send(JSON.stringify({
            action: 'webrtc_ice_candidate',
            candidate: event.candidate
        }));
    }
};

// 7. End call
await fetch(`/api/conversations/${convId}/calls/${callId}/end/`, { method: 'POST' });
```

## Next Steps

1. Run Django migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. Update frontend to:
   - Add call initiation button in conversation UI
   - Create call UI with RTCPeerConnection handling
   - Display incoming call notifications
   - Show call duration timer
   - Add call history view

3. Implement frontend WebRTC handling with:
   - Offer/answer SDP exchange
   - ICE candidate gathering and exchange
   - Media stream management
   - Connection state monitoring

4. (Optional) Add call recording functionality

5. (Optional) Implement group calling with multiple participants

## Call Status Flow

```
initiated → ringing → answered → ended
                   ↘ rejected
                   ↘ missed
                   ↘ no_answer
```

## Architecture Notes

- **REST API**: Used for call initiation, state changes, and history
- **Chat WebSocket**: Used for in-conversation call notifications and signaling
- **Call Signaling WebSocket**: Dedicated channel for peer-to-peer WebRTC signaling
- **Models**: Tracks all call metadata for history and analytics
- **No file storage required**: WebRTC streams are peer-to-peer, no server-side recording (can be added later)
