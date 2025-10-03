from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True  # Изменено с orm_mode

class PreferencesBase(BaseModel):
    preferred_categories: Optional[List[str]] = None
    min_duration_minutes: Optional[int] = 0
    max_duration_minutes: Optional[int] = 120
    preferred_languages: Optional[List[str]] = None
    exclude_explicit_content: Optional[bool] = False
    educational_preference: Optional[bool] = False
    entertainment_preference: Optional[bool] = True

class PreferencesCreate(PreferencesBase):
    pass

class PreferencesResponse(PreferencesBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class VideoAnalysisRequest(BaseModel):
    video_url: str
    user_preferences: dict