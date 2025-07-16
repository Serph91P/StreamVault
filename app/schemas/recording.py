from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict, Any
from enum import Enum

class CleanupPolicyType(str, Enum):
    COUNT = 'count'
    SIZE = 'size'
    AGE = 'age'
    CUSTOM = 'custom'

class PreserveTimeframeSchema(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    weekdays: Optional[List[int]] = None
    timeOfDay: Optional[Dict[str, str]] = None

class CleanupPolicySchema(BaseModel):
    type: CleanupPolicyType = CleanupPolicyType.COUNT
    threshold: int = Field(default=10, description="Threshold value for the policy")
    preserve_favorites: bool = Field(default=True, description="Preserve recordings of favorite categories")
    preserve_categories: Optional[List[str]] = Field(default=None, description="Categories to preserve")
    preserve_timeframe: Optional[PreserveTimeframeSchema] = Field(default=None, description="Timeframe to preserve")

class RecordingSettingsSchema(BaseModel):
    enabled: bool = Field(default=True, description="Enable recording globally")
    output_directory: str = Field(default="/recordings", description="Directory to save recordings")
    filename_template: str = Field(default="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}", 
                                  description="Template for recording filenames")
    filename_preset: Optional[str] = Field(default="default", description="Preset template for recording filenames")
    default_quality: str = Field(default="best", description="Default recording quality")
    use_chapters: bool = Field(default=True, description="Create chapters based on stream events")
    use_category_as_chapter_title: bool = Field(default=False, description="Use category name as chapter title instead of stream title")
    max_streams_per_streamer: int = Field(default=0, description="Maximum number of streams to keep per streamer (0 = unlimited)")
    cleanup_policy: Optional[CleanupPolicySchema] = None

    class Config:
        from_attributes = True

class StreamerRecordingSettingsSchema(BaseModel):
    streamer_id: int
    username: Optional[str] = None
    profile_image_url: Optional[str] = None
    enabled: bool = True
    quality: Optional[str] = None
    custom_filename: Optional[str] = None
    max_streams: Optional[int] = None
    cleanup_policy: Optional[CleanupPolicySchema] = None

    class Config:
        from_attributes = True
        
class ActiveRecordingSchema(BaseModel):
    streamer_id: int
    streamer_name: str
    started_at: str
    duration: float
    output_path: str
    quality: str
    
class StorageUsageSchema(BaseModel):
    totalSize: int
    recordingCount: int
    oldestRecording: str
    newestRecording: str
    
class CleanupResultSchema(BaseModel):
    status: str
    message: str
    deleted_count: int
    deleted_paths: List[str]
