"""
Celery Tasks for Async Match Processing
"""
from celery import Celery
from typing import Dict, List
import os
import time
import asyncio
from collections import Counter

from .models import MatchTier, CommunityMatch, MatchResult, SanitizedProfile
from .database import db_manager
from .ai_services import ai_service
from .cache import cache_manager


# Initialize Celery
celery_app = Celery(
    "matching_system",
    broker=os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_BACKEND_URL", "redis://localhost:6379/1")
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=10,  # 10 second hard limit
    task_soft_time_limit=8  # 8 second soft limit
)


def run_async(coro):
    """Helper to run async functions in Celery"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="process_match_task", bind=True)
def process_match_task(self, user_data: Dict) -> Dict:
    """
    Main Celery Task: Hybrid Matching Algorithm
    
    Phases:
    1. Sanitization (LLM)
    2. Vectorization (OpenAI Embeddings)
    3. Hybrid Matching:
       - Filter by City + Timezone (SQL)
       - Vector Search (Pinecone)
       - Diversity Injection
    4. Decision Engine (Soulmate/Explorer/Fallback)
    5. AI Intro (if Soulmate)
    """
    start_time = time.time()
    task_id = self.request.id
    
    try:
        # Update task state
        self.update_state(state='PROCESSING', meta={'step': 'sanitization'})
        
        # PHASE 1: Sanitization & Enrichment
        sanitized_bio, enriched_tags, pii_removed = run_async(
            ai_service.sanitize_and_enrich_profile(
                user_data["bio"],
                user_data["interest_tags"]
            )
        )
        
        sanitized_profile = SanitizedProfile(
            user_id=user_data["user_id"],
            sanitized_bio=sanitized_bio,
            enriched_tags=enriched_tags,
            city=user_data["city"],
            timezone=user_data["timezone"],
            pii_removed=pii_removed
        )
        
        self.update_state(state='PROCESSING', meta={'step': 'vectorization'})
        
        # PHASE 2: Vectorization
        embedding_text = ai_service.create_embedding_payload(
            sanitized_bio, 
            enriched_tags
        )
        user_vector = run_async(ai_service.generate_embedding(embedding_text))
        
        # Cache user vector (7-day TTL)
        cache_manager.set_user_vector(user_data["user_id"], user_vector, ttl=604800)
        
        self.update_state(state='PROCESSING', meta={'step': 'hybrid_matching'})
        
        # PHASE 3: Hybrid Matching
        matches = run_async(_hybrid_matching_algorithm(
            user_vector=user_vector,
            city=sanitized_profile.city,
            timezone=sanitized_profile.timezone
        ))
        
        self.update_state(state='PROCESSING', meta={'step': 'decision_engine'})
        
        # PHASE 4: Decision Engine
        result = run_async(_apply_decision_engine(
            task_id=task_id,
            user_id=user_data["user_id"],
            user_bio=sanitized_bio,
            matches=matches
        ))
        
        processing_time = int((time.time() - start_time) * 1000)
        result.processing_time_ms = processing_time
        
        # Publish to WebSocket
        cache_manager.publish_match_result(user_data["user_id"], result.dict())
        
        return result.dict()
        
    except Exception as e:
        self.update_state(state='FAILED', meta={'error': str(e)})
        raise


async def _hybrid_matching_algorithm(
    user_vector: List[float],
    city: str,
    timezone: str
) -> List[Dict]:
    """
    Hybrid Matching Algorithm - 3 Steps:
    A) Filter by location (SQL)
    B) Vector search on filtered subset (Pinecone)
    C) Diversity injection
    """
    # STEP A: Filter by City + Timezone (reduces by ~95%)
    filtered_communities = await db_manager.filter_communities_by_location(
        city=city,
        timezone=timezone,
        limit=1000
    )
    
    if not filtered_communities:
        # No location matches, fallback to popular
        return await db_manager.get_popular_communities(limit=5)
    
    # Extract community IDs for vector search
    community_ids = [c["community_id"] for c in filtered_communities]
    
    # STEP B: Cosine Similarity Search (Top 20)
    vector_matches = db_manager.vector_search(
        query_vector=user_vector,
        community_ids=community_ids,
        top_k=20
    )
    
    # Merge vector scores with community details
    community_map = {c["community_id"]: c for c in filtered_communities}
    
    enriched_matches = []
    for vm in vector_matches:
        comm_id = vm["community_id"]
        if comm_id in community_map:
            community = community_map[comm_id]
            enriched_matches.append({
                "community_id": comm_id,
                "community_name": community["community_name"],
                "category": community["category"],
                "match_score": vm["match_score"],
                "member_count": community["member_count"],
                "recent_activity": community["recent_activity"]
            })
    
    # STEP C: Diversity Injection
    enriched_matches = _apply_diversity_filter(enriched_matches)
    
    return enriched_matches


def _apply_diversity_filter(matches: List[Dict]) -> List[Dict]:
    """
    Phase 3C: Diversity Injection
    If top 3 matches are same category, inject 1 diverse match
    """
    if len(matches) < 4:
        return matches
    
    top_3_categories = [m["category"] for m in matches[:3]]
    category_counts = Counter(top_3_categories)
    
    # Check if top 3 are all same category
    if len(category_counts) == 1:
        # Find first diverse match (different category)
        dominant_category = top_3_categories[0]
        
        for i in range(3, len(matches)):
            if matches[i]["category"] != dominant_category:
                # Inject diverse match at position 2
                diverse_match = matches.pop(i)
                matches.insert(2, diverse_match)
                break
    
    return matches


async def _apply_decision_engine(
    task_id: str,
    user_id: str,
    user_bio: str,
    matches: List[Dict]
) -> MatchResult:
    """
    Decision Engine: Apply thresholds and determine tier
    
    Thresholds:
    - Soulmate (>0.87): Auto-join + AI Intro
    - Explorer (0.55-0.87): Show 3-5 options
    - Fallback (<0.55): Popular groups + profile update request
    """
    if not matches:
        # No matches at all
        popular = await db_manager.get_popular_communities(limit=5)
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.FALLBACK,
            matches=[_to_community_match(c, 0.0) for c in popular],
            requires_profile_update=True,
            processing_time_ms=0
        )
    
    top_match = matches[0]
    top_score = top_match["match_score"]
    
    # SOULMATE TIER (>0.87)
    if top_score > 0.87:
        # Auto-join community
        joined = await db_manager.auto_join_community(user_id, top_match["community_id"])
        
        # Generate AI Introduction
        ai_intro_generated = False
        if joined:
            active_members = await db_manager.get_community_members_for_intro(
                top_match["community_id"],
                limit=5
            )
            
            # Get community details for intro
            community_details = await db_manager.get_community_details([top_match["community_id"]])
            community = community_details.get(top_match["community_id"], {})
            
            intro_text, mentioned_member, toxicity = await ai_service.generate_ai_introduction(
                user_bio=user_bio,
                community_name=top_match["community_name"],
                community_description=community.get("description", ""),
                active_members=active_members
            )
            
            # Only post if toxicity is acceptable
            if toxicity < 0.75:
                # Here you would post the intro to the community
                # await post_intro_to_community(community_id, intro_text)
                ai_intro_generated = True
        
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.SOULMATE,
            matches=[_to_community_match(top_match)],
            auto_joined_community=top_match["community_id"],
            ai_intro_generated=ai_intro_generated,
            processing_time_ms=0
        )
    
    # EXPLORER TIER (0.55 - 0.87)
    elif top_score >= 0.55:
        # Show 3-5 options
        explorer_matches = matches[:5]
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.EXPLORER,
            matches=[_to_community_match(m) for m in explorer_matches],
            processing_time_ms=0
        )
    
    # FALLBACK TIER (<0.55)
    else:
        # Show popular + request profile update
        popular = await db_manager.get_popular_communities(limit=5)
        return MatchResult(
            task_id=task_id,
            user_id=user_id,
            tier=MatchTier.FALLBACK,
            matches=[_to_community_match(c, 0.0) for c in popular],
            requires_profile_update=True,
            processing_time_ms=0
        )


def _to_community_match(community: Dict, score: float = None) -> CommunityMatch:
    """Convert dict to CommunityMatch model"""
    return CommunityMatch(
        community_id=community["community_id"],
        community_name=community["community_name"],
        category=community["category"],
        match_score=score if score is not None else community.get("match_score", 0.0),
        member_count=community["member_count"],
        recent_activity=community.get("recent_activity", 0)
    )
