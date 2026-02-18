"""
Initialize Python package
"""
from .api import app
from .celery_tasks import celery_app, process_match_task
from .models import (
    UserProfileInput,
    MatchResult,
    MatchTier,
    CommunityMatch,
    TaskStatusResponse
)

__version__ = "2.0.0"
__all__ = [
    "app",
    "celery_app",
    "process_match_task",
    "UserProfileInput",
    "MatchResult",
    "MatchTier",
    "CommunityMatch",
    "TaskStatusResponse"
]
