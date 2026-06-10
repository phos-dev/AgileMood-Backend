from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


class FeedbackBase(BaseModel):
    message: str
    emotion_record_id: int
    is_anonymous: bool = False
    
    class Config:
        from_attributes = True


class FeedbackCreate(FeedbackBase):
    pass


class FeedbackInDb(FeedbackBase):
    id: int
    manager_id: int
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        from_attributes = True


class FeedbackResponse(FeedbackInDb):
    manager_knows_identity: bool = False
    emotion_name: Optional[str] = None
    emotion_notes: Optional[str] = None
    emotion_intensity: Optional[int] = None


class AllFeedbacksResponse(BaseModel):
    feedbacks: List[FeedbackResponse] 