from pydantic import BaseModel, Field
from typing import Optional, List

class RecordingSettingsSchema(BaseModel):
    enabled: bool = Field(default=True, description="Enable recording globally")
    output_directory: str = Field(default="/recordings", description="Directory to save recordings")
    filename_template: str = Field(default="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}", 
                                  description="Template for recording filenames")
    default_quality: str = Field(default="best", description="Default recording quality")
    use_chapters: bool = Field(default=True, description="Create chapters based on stream events")
    max_concurrent_recordings: int = Field(default=3, description="Maximum concurrent recordings")
    use_category_as_chapter_title: bool = Field(default=False, description="Use category name as chapter title instead of stream title")

    class Config:
        from_attributes = True
class StreamerRecordingSettingsSchema(BaseModel):
    streamer_id: int
    username: Optional[str] = None
    profile_image_url: Optional[str] = None
    enabled: bool = True
    quality: Optional[str] = None
    custom_filename: Optional[str] = None

    class Config:
        from_attributes = True
class ActiveRecordingSchema(BaseModel):
    streamer_id: int
    streamer_name: str
    started_at: str
    duration: float
    output_path: str
    quality: str
