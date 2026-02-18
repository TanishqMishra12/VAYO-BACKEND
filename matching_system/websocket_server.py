"""
WebSocket Server for Real-time Match Result Delivery
Uses Socket.io + Redis Pub/Sub for instant notifications
"""
import socketio
import asyncio
import json
import logging
from typing import Dict, Set
import redis.asyncio as aioredis
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # Configure based on your frontend domain
    logger=True,
    engineio_logger=False
)

# Track active connections per user
active_connections: Dict[str, Set[str]] = {}  # {user_id: {sid1, sid2, ...}}

# Redis Pub/Sub client
redis_pubsub = None
redis_client = None


async def initialize_redis():
    """Initialize Redis Pub/Sub connection"""
    global redis_pubsub, redis_client
    
    redis_url = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")
    redis_client = await aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    
    redis_pubsub = redis_client.pubsub()
    logger.info("✓ Redis Pub/Sub initialized")


async def redis_listener():
    """
    Background task: Listen to Redis Pub/Sub and broadcast to WebSocket clients
    Subscribes to pattern: match_updates_*
    """
    if not redis_pubsub:
        await initialize_redis()
    
    # Subscribe to all match update channels
    await redis_pubsub.psubscribe("match_updates_*")
    logger.info("✓ Subscribed to match_updates_* channels")
    
    try:
        async for message in redis_pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                data = message["data"]
                
                # Extract user_id from channel name (match_updates_{user_id})
                user_id = channel.replace("match_updates_", "")
                
                logger.info(f"📨 Received match result for user: {user_id}")
                
                # Parse the match result
                try:
                    match_result = json.loads(data) if isinstance(data, str) else data
                    
                    # Broadcast to all connected clients for this user
                    await broadcast_to_user(user_id, match_result)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse match result: {e}")
                    
    except Exception as e:
        logger.error(f"Redis listener error: {e}")
        # Attempt to reconnect
        await asyncio.sleep(5)
        await redis_listener()


async def broadcast_to_user(user_id: str, match_result: dict):
    """
    Broadcast match result to all WebSocket connections for a specific user
    """
    if user_id not in active_connections:
        logger.warning(f"No active connections for user: {user_id}")
        return
    
    sids = active_connections[user_id].copy()
    
    for sid in sids:
        try:
            await sio.emit(
                'match_result',
                {
                    'status': 'completed',
                    'result': match_result
                },
                room=sid
            )
            logger.info(f"✓ Sent match result to {user_id} (sid: {sid[:8]}...)")
            
        except Exception as e:
            logger.error(f"Failed to send to {sid}: {e}")
            # Remove stale connection
            active_connections[user_id].discard(sid)


@sio.event
async def connect(sid, environ, auth):
    """
    Handle new WebSocket connection
    Client must provide user_id in auth parameter
    """
    try:
        # Extract user_id from auth
        user_id = auth.get('user_id') if auth else None
        
        if not user_id:
            logger.warning(f"Connection rejected - no user_id provided (sid: {sid})")
            return False  # Reject connection
        
        # Track connection
        if user_id not in active_connections:
            active_connections[user_id] = set()
        
        active_connections[user_id].add(sid)
        
        # Store user_id in session for later use
        async with sio.session(sid) as session:
            session['user_id'] = user_id
        
        logger.info(f"✓ Client connected: {user_id} (sid: {sid[:8]}...) - Total: {len(active_connections[user_id])}")
        
        # Send connection acknowledgment
        await sio.emit('connection_status', {
            'status': 'connected',
            'user_id': user_id,
            'message': 'Ready to receive match updates'
        }, room=sid)
        
        return True
        
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False


@sio.event
async def disconnect(sid):
    """Handle WebSocket disconnection"""
    try:
        # Get user_id from session
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
        
        if user_id and user_id in active_connections:
            active_connections[user_id].discard(sid)
            
            # Clean up empty sets
            if not active_connections[user_id]:
                del active_connections[user_id]
            
            logger.info(f"✓ Client disconnected: {user_id} (sid: {sid[:8]}...)")
        
    except Exception as e:
        logger.error(f"Disconnect error: {e}")


@sio.event
async def ping(sid):
    """
    Heartbeat/ping mechanism
    Client sends 'ping', server responds with 'pong'
    """
    await sio.emit('pong', {'timestamp': asyncio.get_event_loop().time()}, room=sid)


@sio.event
async def subscribe_match(sid, data):
    """
    Subscribe to match updates for a specific task
    Client can call this after initiating a match request
    """
    try:
        task_id = data.get('task_id')
        
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
        
        if not task_id or not user_id:
            await sio.emit('error', {
                'message': 'Missing task_id or user_id'
            }, room=sid)
            return
        
        logger.info(f"📍 User {user_id} subscribed to task {task_id}")
        
        await sio.emit('subscription_confirmed', {
            'task_id': task_id,
            'channel': f'match_updates_{user_id}'
        }, room=sid)
        
    except Exception as e:
        logger.error(f"Subscribe error: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)


async def start_background_tasks():
    """Start background tasks (Redis listener)"""
    asyncio.create_task(redis_listener())
    logger.info("✓ Background tasks started")


async def cleanup():
    """Cleanup resources on shutdown"""
    global redis_pubsub, redis_client
    
    if redis_pubsub:
        await redis_pubsub.unsubscribe()
        await redis_pubsub.close()
    
    if redis_client:
        await redis_client.close()
    
    logger.info("✓ WebSocket server cleanup completed")


# Export for integration with FastAPI
__all__ = ['sio', 'initialize_redis', 'start_background_tasks', 'cleanup']
