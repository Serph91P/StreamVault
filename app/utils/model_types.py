"""
Model type annotation helpers for SQLAlchemy relationships.

This module provides TypeVar and Protocol definitions to properly annotate 
SQLAlchemy relationships in a way that mypy can understand.
"""

from typing import TypeVar, List, Optional, Generic, Protocol, Dict, Any, cast
from datetime import datetime

# Create TypeVars for each model type
T_Streamer = TypeVar('T_Streamer', bound='Streamer')
T_Stream = TypeVar('T_Stream', bound='Stream')
T_StreamEvent = TypeVar('T_StreamEvent', bound='StreamEvent')
T_StreamMetadata = TypeVar('T_StreamMetadata', bound='StreamMetadata')
T_User = TypeVar('T_User', bound='User')
T_Category = TypeVar('T_Category', bound='Category')
T_FavoriteCategory = TypeVar('T_FavoriteCategory', bound='FavoriteCategory')
T_NotificationSettings = TypeVar('T_NotificationSettings', bound='NotificationSettings')
T_GlobalSettings = TypeVar('T_GlobalSettings', bound='GlobalSettings')
T_SystemConfig = TypeVar('T_SystemConfig', bound='SystemConfig')
T_PushSubscription = TypeVar('T_PushSubscription', bound='PushSubscription')
T_RecordingSettings = TypeVar('T_RecordingSettings', bound='RecordingSettings')
T_StreamerRecordingSettings = TypeVar('T_StreamerRecordingSettings', bound='StreamerRecordingSettings')

# Type protocols for models
class Streamer(Protocol):
    """Protocol for Streamer model"""
    id: int
    username: str
    display_name: Optional[str]
    profile_image_url: Optional[str]
    streams: List['Stream']
    streamer_recording_settings: Optional['StreamerRecordingSettings']
    
class Stream(Protocol):
    """Protocol for Stream model"""
    id: int
    streamer_id: int
    streamer: 'Streamer'
    stream_metadata: Optional['StreamMetadata']
    events: List['StreamEvent']
    
class StreamEvent(Protocol):
    """Protocol for StreamEvent model"""
    id: int
    stream_id: int
    stream: 'Stream'

class StreamMetadata(Protocol):
    """Protocol for StreamMetadata model"""
    id: int
    stream_id: int
    stream: 'Stream'

class User(Protocol):
    """Protocol for User model"""
    id: int
    username: str
    notification_settings: Optional['NotificationSettings']
    favorite_categories: List['FavoriteCategory']

class Category(Protocol):
    """Protocol for Category model"""
    id: int
    name: str
    favorites: List['FavoriteCategory']
    
class FavoriteCategory(Protocol):
    """Protocol for FavoriteCategory model"""
    id: int
    user_id: int
    category_id: int
    user: 'User'
    category: 'Category'

class NotificationSettings(Protocol):
    """Protocol for NotificationSettings model"""
    id: int
    user_id: int
    user: 'User'
    
class GlobalSettings(Protocol):
    """Protocol for GlobalSettings model"""
    id: int
    http_proxy: Optional[str]
    https_proxy: Optional[str]

class SystemConfig(Protocol):
    """Protocol for SystemConfig model"""
    key: str
    value: str

class PushSubscription(Protocol):
    """Protocol for PushSubscription model"""
    id: int
    subscription_json: str

class RecordingSettings(Protocol):
    """Protocol for RecordingSettings model"""
    id: int
    streamer: Optional['Streamer']

class StreamerRecordingSettings(Protocol):
    """Protocol for StreamerRecordingSettings model"""
    id: int
    streamer_id: int
    streamer: 'Streamer'
