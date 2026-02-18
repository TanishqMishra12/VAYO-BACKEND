"""
Example Usage & Testing Script
Demonstrates the AI-Powered Community Matching System
"""
import asyncio
import httpx
import time


async def test_matching_system():
    """
    Complete workflow test for the matching system
    """
    base_url = "http://localhost:8000/api/v1"
    
    print("=" * 60)
    print("AI-Powered Community Matching System - Test Suite")
    print("=" * 60)
    
    # Test 1: Health Check
    print("\n[1] Testing Health Check...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/health")
        print(f"✓ Health Status: {response.json()}")
    
    # Test 2: Initiate Match Request (Soulmate Scenario)
    print("\n[2] Testing Soulmate Match (>0.87 similarity)...")
    soulmate_profile = {
        "user_id": "user_soulmate_001",
        "bio": "Passionate Python developer focusing on AI/ML. I build neural networks daily and love discussing transformer architectures.",
        "interest_tags": ["Python", "AI", "Machine Learning", "Deep Learning", "NLP"],
        "city": "San Francisco",
        "timezone": "America/Los_Angeles"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/match", json=soulmate_profile)
        task_data = response.json()
        print(f"✓ Task ID: {task_data['task_id']}")
        print(f"✓ WebSocket Channel: {task_data['websocket_channel']}")
        print(f"✓ Estimated Time: {task_data['estimated_time_ms']}ms")
        
        # Poll for result
        task_id = task_data['task_id']
        max_attempts = 15
        
        for attempt in range(max_attempts):
            time.sleep(0.5)
            try:
                result_response = await client.get(f"{base_url}/match/{task_id}")
                result = result_response.json()
                
                print(f"\n✓ Match Result:")
                print(f"  Tier: {result['tier'].upper()}")
                print(f"  Processing Time: {result['processing_time_ms']}ms")
                print(f"  Auto-joined: {result.get('auto_joined_community', 'N/A')}")
                print(f"  AI Intro Generated: {result.get('ai_intro_generated', False)}")
                print(f"\n  Top Matches:")
                for i, match in enumerate(result['matches'][:3], 1):
                    print(f"    {i}. {match['community_name']} - Score: {match['match_score']:.3f}")
                    print(f"       Category: {match['category']} | Members: {match['member_count']}")
                break
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 202:
                    print(f"  [Attempt {attempt + 1}] Still processing...")
                else:
                    raise
    
    # Test 3: Explorer Scenario (0.55-0.87)
    print("\n[3] Testing Explorer Match (0.55-0.87 similarity)...")
    explorer_profile = {
        "user_id": "user_explorer_002",
        "bio": "Tech enthusiast interested in various programming topics. Learning web development and dabbling in data science.",
        "interest_tags": ["Programming", "Web Dev", "Data Science"],
        "city": "New York",
        "timezone": "America/New_York"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/match", json=explorer_profile)
        task_id = response.json()['task_id']
        
        # Wait and fetch result
        time.sleep(2.5)
        result_response = await client.get(f"{base_url}/match/{task_id}")
        result = result_response.json()
        
        print(f"✓ Tier: {result['tier'].upper()}")
        print(f"✓ Options Presented: {len(result['matches'])}")
        print(f"✓ Score Range: {result['matches'][0]['match_score']:.3f} - {result['matches'][-1]['match_score']:.3f}")
    
    # Test 4: Fallback Scenario (<0.55)
    print("\n[4] Testing Fallback Match (<0.55 similarity)...")
    fallback_profile = {
        "user_id": "user_fallback_003",
        "bio": "Just joined, still figuring things out.",
        "interest_tags": ["General"],
        "city": "Austin",
        "timezone": "America/Chicago"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/match", json=fallback_profile)
        task_id = response.json()['task_id']
        
        time.sleep(2.5)
        result_response = await client.get(f"{base_url}/match/{task_id}")
        result = result_response.json()
        
        print(f"✓ Tier: {result['tier'].upper()}")
        print(f"✓ Profile Update Required: {result['requires_profile_update']}")
        print(f"✓ Popular Communities Shown: {len(result['matches'])}")
    
    # Test 5: Get Popular Communities
    print("\n[5] Testing Popular Communities Endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/popular-communities?limit=3")
        communities = response.json()['communities']
        print(f"✓ Retrieved {len(communities)} popular communities")
        for comm in communities:
            print(f"  - {comm['community_name']} ({comm['member_count']} members)")
    
    print("\n" + "=" * 60)
    print("✅ All Tests Completed Successfully!")
    print("=" * 60)


def test_hybrid_matching_logic():
    """
    Unit test for hybrid matching algorithm components
    """
    print("\n[UNIT TEST] Hybrid Matching Algorithm Components")
    print("-" * 60)
    
    # Test diversity filter
    from matching_system.celery_tasks import _apply_diversity_filter
    
    # Scenario 1: All same category (should inject diversity)
    matches = [
        {"community_id": "1", "category": "Programming", "match_score": 0.95},
        {"community_id": "2", "category": "Programming", "match_score": 0.92},
        {"community_id": "3", "category": "Programming", "match_score": 0.89},
        {"community_id": "4", "category": "Gaming", "match_score": 0.86},  # Will be injected
        {"community_id": "5", "category": "Programming", "match_score": 0.84},
    ]
    
    result = _apply_diversity_filter(matches)
    
    print("\n✓ Diversity Filter Test:")
    print(f"  Original Top 3: {[m['category'] for m in matches[:3]]}")
    print(f"  After Diversity: {[m['category'] for m in result[:3]]}")
    
    assert result[2]['category'] == "Gaming", "Diversity injection failed!"
    print("  ✓ Diversity injection working correctly!")
    
    # Scenario 2: Already diverse (no change needed)
    diverse_matches = [
        {"community_id": "1", "category": "Programming", "match_score": 0.95},
        {"community_id": "2", "category": "Gaming", "match_score": 0.92},
        {"community_id": "3", "category": "Art", "match_score": 0.89},
    ]
    
    result2 = _apply_diversity_filter(diverse_matches)
    assert result2 == diverse_matches, "Should not modify already diverse matches!"
    print("  ✓ No modification for diverse matches - correct!")


if __name__ == "__main__":
    # Run async tests
    print("\n🚀 Starting Integration Tests...")
    asyncio.run(test_matching_system())
    
    # Run unit tests
    print("\n🧪 Starting Unit Tests...")
    test_hybrid_matching_logic()
    
    print("\n✅ All Tests Passed!\n")
