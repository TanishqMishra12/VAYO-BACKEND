"""
AI Services - OpenAI Integration for Sanitization, Vectorization, and Intro Generation
"""
import openai
import os
from typing import List, Dict, Tuple
import json
import re


class AIService:
    """Handles all OpenAI API interactions"""
    
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.embedding_model = "text-embedding-3-small"
        self.chat_model = "gpt-4o-mini"
    
    async def sanitize_and_enrich_profile(
        self, 
        bio: str, 
        interest_tags: List[str]
    ) -> Tuple[str, List[str], bool]:
        """
        Phase 2: Sanitization
        - Strip PII (phone/email)
        - Enrich tags using LLM
        Returns: (sanitized_bio, enriched_tags, pii_removed)
        """
        prompt = f"""You are a profile sanitization assistant. Analyze the following user bio and:
1. Remove any PII (phone numbers, email addresses, physical addresses)
2. Return a cleaned bio
3. Extract and add implied interest tags (e.g., "I code daily" -> add "Programming")
4. Return enriched tags list

Bio: "{bio}"
Current Tags: {interest_tags}

Respond in JSON format:
{{
    "sanitized_bio": "cleaned bio text",
    "enriched_tags": ["tag1", "tag2", ...],
    "pii_found": true/false
}}
"""
        
        try:
            response = openai.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are a data sanitization expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return (
                result["sanitized_bio"],
                result["enriched_tags"],
                result["pii_found"]
            )
        except Exception as e:
            # Fallback: Basic PII removal regex
            sanitized_bio = self._basic_pii_removal(bio)
            return (sanitized_bio, interest_tags, False)
    
    def _basic_pii_removal(self, text: str) -> str:
        """Fallback PII removal using regex"""
        # Remove email
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email removed]', text)
        # Remove phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[phone removed]', text)
        return text
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Phase 3: Vectorization
        Generate 1536D embedding using text-embedding-3-small
        """
        response = openai.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        
        return response.data[0].embedding
    
    def create_embedding_payload(self, bio: str, tags: List[str]) -> str:
        """
        Combine Bio + Interest Tags into single text payload
        Format: "Bio: {bio}\nInterests: {tag1, tag2, tag3}"
        """
        tags_text = ", ".join(tags)
        return f"Bio: {bio}\nInterests: {tags_text}"
    
    async def generate_ai_introduction(
        self, 
        user_bio: str, 
        community_name: str,
        community_description: str,
        active_members: List[Dict]
    ) -> Tuple[str, str, float]:
        """
        Generate AI introduction for Soulmate matches
        Returns: (intro_text, mentioned_member, toxicity_score)
        """
        # Pick most active member for @mention
        mentioned_member = active_members[0]["username"] if active_members else None
        
        prompt = f"""Generate a friendly, non-corporate introduction for a new community member.

Community: {community_name}
Description: {community_description}
New Member Bio: {user_bio}
Active Member to Mention: @{mentioned_member}

Requirements:
- Maximum 3 sentences
- Mention @{mentioned_member} naturally
- Highlight shared interests
- Sound warm and welcoming, not corporate

Generate only the introduction text, no explanations."""
        
        try:
            response = openai.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are a community onboarding assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            intro_text = response.choices[0].message.content.strip()
            
            # Run toxicity check
            toxicity_score = await self._check_toxicity(intro_text)
            
            return (intro_text, mentioned_member, toxicity_score)
            
        except Exception as e:
            # Fallback generic intro
            return (
                f"Welcome to {community_name}! We're excited to have you here.",
                None,
                0.0
            )
    
    async def _check_toxicity(self, text: str) -> float:
        """
        Check text toxicity using OpenAI moderation API
        Returns score 0.0-1.0
        """
        try:
            response = openai.moderations.create(input=text)
            
            # Get highest category score
            scores = [
                response.results[0].category_scores.hate,
                response.results[0].category_scores.harassment,
                response.results[0].category_scores.violence,
                response.results[0].category_scores.sexual
            ]
            
            return max(scores)
        except Exception:
            return 0.0


# Global instance
ai_service = AIService()
