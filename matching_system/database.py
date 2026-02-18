"""
Database Layer - PostgreSQL & Pinecone Integration
"""
import asyncpg
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Optional, Tuple
import os
from datetime import datetime, timedelta


class DatabaseManager:
    """Manages PostgreSQL and Pinecone connections"""
    
    def __init__(self):
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.pinecone_client = None
        self.pinecone_index = None
        
    async def initialize_postgres(self):
        """Initialize PostgreSQL connection pool"""
        self.pg_pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD"),
            database=os.getenv("POSTGRES_DB", "community_matching"),
            min_size=10,
            max_size=50,
            command_timeout=5
        )
        
    def initialize_pinecone(self):
        """Initialize Pinecone vector database"""
        api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_client = Pinecone(api_key=api_key)
        
        index_name = os.getenv("PINECONE_INDEX_NAME", "community-vectors")
        
        # Create index if it doesn't exist
        if index_name not in self.pinecone_client.list_indexes().names():
            self.pinecone_client.create_index(
                name=index_name,
                dimension=1536,  # text-embedding-3-small dimension
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        
        self.pinecone_index = self.pinecone_client.Index(index_name)
    
    async def filter_communities_by_location(
        self, 
        city: str, 
        timezone: str, 
        limit: int = 1000
    ) -> List[Dict]:
        """
        Phase 1: SQL filtering by City + Timezone
        Reduces search space by ~95%
        """
        query = """
            SELECT 
                c.community_id,
                c.community_name,
                c.category,
                c.member_count,
                c.city,
                c.timezone,
                COALESCE(ca.message_count, 0) as recent_activity
            FROM communities c
            LEFT JOIN (
                SELECT 
                    community_id, 
                    COUNT(*) as message_count
                FROM community_activity
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY community_id
            ) ca ON c.community_id = ca.community_id
            WHERE 
                c.city = $1 
                AND c.timezone = $2
                AND c.is_active = true
            ORDER BY c.member_count DESC, ca.message_count DESC
            LIMIT $3;
        """
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, city, timezone, limit)
            return [dict(row) for row in rows]
    
    def vector_search(
        self, 
        query_vector: List[float], 
        community_ids: List[str], 
        top_k: int = 20
    ) -> List[Dict]:
        """
        Phase 2: Cosine similarity search on filtered subset
        Returns top_k matches with scores
        """
        # Filter parameter restricts search to pre-filtered community IDs
        results = self.pinecone_index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter={"community_id": {"$in": community_ids}}
        )
        
        matches = []
        for match in results.matches:
            matches.append({
                "community_id": match.metadata.get("community_id"),
                "match_score": float(match.score),
                "metadata": match.metadata
            })
        
        return matches
    
    async def get_community_details(self, community_ids: List[str]) -> Dict[str, Dict]:
        """Fetch full community details from PostgreSQL"""
        query = """
            SELECT 
                community_id,
                community_name,
                category,
                member_count,
                description
            FROM communities
            WHERE community_id = ANY($1::text[]);
        """
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, community_ids)
            return {row['community_id']: dict(row) for row in rows}
    
    async def get_popular_communities(self, limit: int = 5) -> List[Dict]:
        """Fallback: Get general popular communities"""
        query = """
            SELECT 
                c.community_id,
                c.community_name,
                c.category,
                c.member_count,
                COALESCE(ca.message_count, 0) as recent_activity
            FROM communities c
            LEFT JOIN (
                SELECT 
                    community_id, 
                    COUNT(*) as message_count
                FROM community_activity
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY community_id
            ) ca ON c.community_id = ca.community_id
            WHERE c.is_active = true
            ORDER BY c.member_count DESC, ca.message_count DESC
            LIMIT $1;
        """
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
            return [dict(row) for row in rows]
    
    async def auto_join_community(self, user_id: str, community_id: str) -> bool:
        """Auto-join user to community (Soulmate tier)"""
        query = """
            INSERT INTO community_members (user_id, community_id, joined_at, auto_joined)
            VALUES ($1, $2, NOW(), true)
            ON CONFLICT (user_id, community_id) DO NOTHING
            RETURNING user_id;
        """
        
        async with self.pg_pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, community_id)
            return result is not None
    
    async def get_community_members_for_intro(
        self, 
        community_id: str, 
        limit: int = 5
    ) -> List[Dict]:
        """Get active members for AI intro @mention"""
        query = """
            SELECT 
                u.user_id,
                u.username,
                u.bio,
                COUNT(ca.message_id) as message_count
            FROM users u
            JOIN community_members cm ON u.user_id = cm.user_id
            LEFT JOIN community_activity ca ON ca.user_id = u.user_id 
                AND ca.community_id = $1
                AND ca.created_at >= NOW() - INTERVAL '7 days'
            WHERE cm.community_id = $1
            GROUP BY u.user_id, u.username, u.bio
            ORDER BY message_count DESC
            LIMIT $2;
        """
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, community_id, limit)
            return [dict(row) for row in rows]
    
    async def close(self):
        """Close database connections"""
        if self.pg_pool:
            await self.pg_pool.close()


# Global instance
db_manager = DatabaseManager()
