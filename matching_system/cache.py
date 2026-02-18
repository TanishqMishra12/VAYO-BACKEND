"""
Redis Cache Manager for Vectors and Results
"""
import redis
import json
import pickle
from typing import List, Optional, Dict
import os


class CacheManager:
    """Manages Redis caching for vectors and results"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=2,  # Separate DB for caching
            decode_responses=False  # Binary mode for pickle
        )
        
        self.pubsub_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=3,  # Separate DB for pub/sub
            decode_responses=True
        )
    
    def set_user_vector(self, user_id: str, vector: List[float], ttl: int = 604800):
        """
        Cache user vector with 7-day TTL (604800 seconds)
        Using pickle for efficient float array storage
        """
        key = f"user_vector:{user_id}"
        self.redis_client.setex(
            key,
            ttl,
            pickle.dumps(vector)
        )
    
    def get_user_vector(self, user_id: str) -> Optional[List[float]]:
        """Retrieve cached user vector"""
        key = f"user_vector:{user_id}"
        data = self.redis_client.get(key)
        
        if data:
            return pickle.loads(data)
        return None
    
    def set_group_vector(self, community_id: str, vector: List[float], ttl: int = 86400):
        """
        Cache group vector with 24-hour TTL (86400 seconds)
        """
        key = f"group_vector:{community_id}"
        self.redis_client.setex(
            key,
            ttl,
            pickle.dumps(vector)
        )
    
    def get_group_vector(self, community_id: str) -> Optional[List[float]]:
        """Retrieve cached group vector"""
        key = f"group_vector:{community_id}"
        data = self.redis_client.get(key)
        
        if data:
            return pickle.loads(data)
        return None
    
    def cache_query_result(self, query_key: str, result: Dict, ttl: int = 900):
        """
        Cache complex query results with 15-min TTL (900 seconds)
        """
        self.redis_client.setex(
            query_key,
            ttl,
            json.dumps(result)
        )
    
    def get_cached_query(self, query_key: str) -> Optional[Dict]:
        """Retrieve cached query result"""
        data = self.redis_client.get(query_key)
        
        if data:
            return json.loads(data)
        return None
    
    def publish_match_result(self, user_id: str, result: Dict):
        """
        Publish match result to WebSocket channel via Redis Pub/Sub
        Channel format: match_updates_{user_id}
        """
        channel = f"match_updates_{user_id}"
        self.pubsub_client.publish(channel, json.dumps(result))
    
    def invalidate_user_cache(self, user_id: str):
        """Invalidate all cached data for a user"""
        pattern = f"user_vector:{user_id}"
        self.redis_client.delete(pattern)


# Global instance
cache_manager = CacheManager()
