"""
WebSocket Client Test - Demonstrates Real-time Match Updates
"""
import socketio
import asyncio
import httpx
import json
import time

# Create Socket.IO client
sio = socketio.AsyncClient(logger=True, engineio_logger=False)


async def test_realtime_matching():
    """
    Test complete workflow:
    1. Connect WebSocket with user_id
    2. Initiate match request via REST API
    3. Receive real-time result via WebSocket
    """
    
    user_id = "test_websocket_user_123"
    base_url = "http://localhost:8000"
    
    print("=" * 60)
    print("WebSocket Real-time Matching Test")
    print("=" * 60)
    
    # Event handlers
    @sio.event
    async def connect():
        print("✓ WebSocket Connected!")
    
    @sio.event
    async def connection_status(data):
        print(f"✓ Connection Status: {data}")
    
    @sio.event
    async def match_result(data):
        print("\n" + "=" * 60)
        print("🎉 REAL-TIME MATCH RESULT RECEIVED!")
        print("=" * 60)
        
        result = data.get('result', {})
        
        print(f"Tier: {result.get('tier', 'N/A').upper()}")
        print(f"Processing Time: {result.get('processing_time_ms', 0)}ms")
        print(f"Auto-joined: {result.get('auto_joined_community', 'N/A')}")
        print(f"AI Intro: {result.get('ai_intro_generated', False)}")
        
        matches = result.get('matches', [])
        if matches:
            print(f"\nTop Matches ({len(matches)}):")
            for i, match in enumerate(matches[:3], 1):
                print(f"  {i}. {match['community_name']}")
                print(f"     Score: {match['match_score']:.3f} | Members: {match['member_count']}")
        
        print("=" * 60)
    
    @sio.event
    async def subscription_confirmed(data):
        print(f"✓ Subscribed to task: {data.get('task_id')}")
    
    @sio.event
    async def pong(data):
        print(f"✓ Pong received (latency check)")
    
    @sio.event
    async def error(data):
        print(f"❌ Error: {data.get('message')}")
    
    @sio.event
    async def disconnect():
        print("✓ WebSocket Disconnected")
    
    try:
        # Step 1: Connect to WebSocket with authentication
        print(f"\n[1] Connecting to WebSocket as user: {user_id}...")
        
        await sio.connect(
            base_url,
            auth={'user_id': user_id},
            transports=['websocket'],
            wait_timeout=10
        )
        
        # Wait for connection to stabilize
        await asyncio.sleep(1)
        
        # Step 2: Test heartbeat
        print("\n[2] Testing heartbeat (ping/pong)...")
        await sio.emit('ping')
        await asyncio.sleep(0.5)
        
        # Step 3: Initiate match request via REST API
        print("\n[3] Initiating match request via REST API...")
        
        profile_data = {
            "user_id": user_id,
            "bio": "Passionate Python and AI developer. I build machine learning models daily and love neural networks.",
            "interest_tags": ["Python", "AI", "Machine Learning", "Deep Learning"],
            "city": "San Francisco",
            "timezone": "America/Los_Angeles"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/match",
                json=profile_data,
                timeout=10.0
            )
            
            if response.status_code != 202:
                print(f"❌ API Error: {response.status_code}")
                print(response.text)
                return
            
            task_response = response.json()
            task_id = task_response['task_id']
            
            print(f"✓ Task ID: {task_id}")
            print(f"✓ WebSocket Channel: {task_response['websocket_channel']}")
            print(f"✓ Estimated Time: {task_response['estimated_time_ms']}ms")
        
        # Step 4: Subscribe to specific task updates (optional)
        print(f"\n[4] Subscribing to task updates...")
        await sio.emit('subscribe_match', {'task_id': task_id})
        
        # Step 5: Wait for real-time result
        print("\n[5] Waiting for real-time match result...")
        print("(WebSocket listener is active - result will appear below)")
        
        # Wait up to 10 seconds for result
        await asyncio.sleep(10)
        
        print("\n[6] Test completed!")
        
    except Exception as e:
        print(f"\n❌ Test Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect
        if sio.connected:
            await sio.disconnect()
        
        print("\n✓ Test session ended")


async def test_multiple_connections():
    """
    Test concurrent connections from same user
    Simulates user opening multiple browser tabs
    """
    print("\n" + "=" * 60)
    print("Testing Multiple Concurrent Connections")
    print("=" * 60)
    
    user_id = "multi_conn_user_456"
    clients = []
    
    try:
        # Create 3 concurrent connections
        for i in range(3):
            client = socketio.AsyncClient()
            
            @client.event
            async def connect():
                print(f"  Client {i+1} connected")
            
            @client.event
            async def match_result(data):
                print(f"  Client {i+1} received result!")
            
            await client.connect(
                "http://localhost:8000",
                auth={'user_id': user_id},
                transports=['websocket']
            )
            
            clients.append(client)
            await asyncio.sleep(0.5)
        
        print(f"\n✓ {len(clients)} concurrent connections established")
        
        # Trigger match
        profile_data = {
            "user_id": user_id,
            "bio": "Web developer interested in React and Node.js",
            "interest_tags": ["JavaScript", "Web Dev"],
            "city": "New York",
            "timezone": "America/New_York"
        }
        
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                "http://localhost:8000/api/v1/match",
                json=profile_data
            )
            
            print(f"✓ Match request sent: {response.json()['task_id']}")
        
        # Wait for results
        await asyncio.sleep(8)
        
    finally:
        # Cleanup
        for client in clients:
            if client.connected:
                await client.disconnect()
        
        print(f"✓ Disconnected {len(clients)} clients")


async def test_connection_resilience():
    """
    Test connection without user_id (should be rejected)
    """
    print("\n" + "=" * 60)
    print("Testing Connection Validation")
    print("=" * 60)
    
    client = socketio.AsyncClient()
    
    try:
        print("Attempting connection without user_id...")
        await client.connect(
            "http://localhost:8000",
            transports=['websocket'],
            wait_timeout=5
        )
        
        print("❌ Connection should have been rejected!")
        
    except Exception as e:
        print(f"✓ Connection correctly rejected: {type(e).__name__}")
    
    finally:
        if client.connected:
            await client.disconnect()


async def main():
    """Run all WebSocket tests"""
    print("\n🚀 Starting WebSocket Test Suite\n")
    
    # Test 1: Basic real-time matching
    await test_realtime_matching()
    
    # Wait between tests
    await asyncio.sleep(2)
    
    # Test 2: Multiple concurrent connections
    await test_multiple_connections()
    
    # Wait between tests
    await asyncio.sleep(2)
    
    # Test 3: Connection validation
    await test_connection_resilience()
    
    print("\n✅ All WebSocket tests completed!\n")


if __name__ == "__main__":
    # Run tests
    asyncio.run(main())
