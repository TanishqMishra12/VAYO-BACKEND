"""
Pydantic Models for AI-Powered Community Matching System
"""
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


class MatchTier(str, Enum):
    """Match quality tiers based on cosine similarity thresholds"""
    SOULMATE = "soulmate"  # >0.87
    EXPLORER = "explorer"  # 0.55-0.87
    FALLBACK = "fallback"  # <0.55


class UserProfileInput(BaseModel):
    """User profile input from frontend"""
    user_id: str = Field(..., description="Unique user identifier")
    bio: str = Field(..., min_length=10, max_length=500, description="User biography")
    interest_tags: List[str] = Field(..., min_items=1, max_items=20, description="User interest tags")
    city: str = Field(..., description="User city for location filtering")
    timezone: str = Field(..., description="User timezone (e.g., 'America/New_York')")
    
    @validator('bio')
    def validate_bio(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Bio must be at least 10 characters')
        return v.strip()
    
    @validator('interest_tags')
    def validate_tags(cls, v):
        # Remove duplicates and normalize
        return list(set([tag.strip().lower() for tag in v if tag.strip()]))


class SanitizedProfile(BaseModel):
    """Profile after LLM sanitization"""
    user_id: str
    sanitized_bio: str
    enriched_tags: List[str]
    city: str
    timezone: str
    pii_removed: bool = False


class CommunityMatch(BaseModel):
    """Individual community match result"""
    community_id: str
    community_name: str
    category: str
    match_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    member_count: int
    recent_activity: int = Field(..., description="Number of messages in last 7 days")
    
    class Config:
        json_schema_extra = {
            "example": {
                "community_id": "comm_123",
                "community_name": "Python Developers NYC",
                "category": "Programming",
                "match_score": 0.92,
                "member_count": 1247,
                "recent_activity": 342
            }
        }


class MatchResult(BaseModel):
    """Final match result returned to user"""
    task_id: str
    user_id: str
    tier: MatchTier
    matches: List[CommunityMatch]
    auto_joined_community: Optional[str] = None  # For Soulmate tier
    ai_intro_generated: bool = False
    requires_profile_update: bool = False
    processing_time_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "user_id": "user_456",
                "tier": "soulmate",
                "matches": [],
                "auto_joined_community": "comm_123",
                "ai_intro_generated": True,
                "requires_profile_update": False,
                "processing_time_ms": 1847
            }
        }


class TaskStatusResponse(BaseModel):
    """Immediate response with task ID"""
    task_id: str
    status: Literal["processing", "completed", "failed"]
    estimated_time_ms: int = 2000
    websocket_channel: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "processing",
                "estimated_time_ms": 2000,
                "websocket_channel": "match_updates_user_456"
            }
        }


class AIIntroduction(BaseModel):
    """AI-generated introduction for community"""
    community_id: str
    intro_text: str = Field(..., max_length=300)
    mentioned_member: Optional[str] = None
    toxicity_score: float = Field(..., ge=0.0, le=1.0)
    approved: bool
    
    @validator('approved')
    def check_toxicity(cls, v, values):
        if 'toxicity_score' in values and values['toxicity_score'] > 0.75:
            return False
        return True
