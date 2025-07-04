"""
Example Service with Type Annotations

This module provides an example of how to create services with proper
type annotations for SQLAlchemy models.
"""

from typing import List, Dict, Any, Optional, Union, TypeVar, cast
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import Streamer
from app.utils.sqlalchemy_typing import get_column_value, set_column_value

class ExampleTypedStreamerService:
    """
    Example service class showing proper type annotations for SQLAlchemy model operations
    """
    
    def __init__(self, db: Session):
        """Initialize the service with a database session"""
        self.db = db
    
    def get_streamer(self, streamer_id: int) -> Optional[Streamer]:
        """Get a streamer by ID with proper typing"""
        return self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
    
    def get_streamer_by_username(self, username: str) -> Optional[Streamer]:
        """Get a streamer by username with proper typing"""
        return self.db.query(Streamer).filter(Streamer.username == username).first()
    
    def update_streamer_title(self, streamer_id: int, title: str) -> Optional[Streamer]:
        """
        Update a streamer's title with proper typing.
        
        This demonstrates how to use the helper functions to maintain proper type checking.
        """
        streamer = self.get_streamer(streamer_id)
        if streamer:
            # This approach works with type checking
            set_column_value(streamer, 'title', title)
            set_column_value(streamer, 'last_updated', datetime.now())
            
            # Instead of:
            # streamer.title = title         # mypy error: "Column" has no attribute "title"
            # streamer.last_updated = datetime.now()  # same error
            
            self.db.commit()
        return streamer
    
    def get_streamer_info(self, streamer_id: int) -> Dict[str, Any]:
        """
        Get streamer information with proper typing
        
        This demonstrates how to use the helper function to access model attributes safely.
        """
        streamer = self.get_streamer(streamer_id)
        if not streamer:
            return {}
        
        # Use helper function for type-safe attribute access
        return {
            'id': get_column_value(streamer, 'id'),
            'username': get_column_value(streamer, 'username'),
            'title': get_column_value(streamer, 'title'),
            'category_name': get_column_value(streamer, 'category_name'),
            'is_live': get_column_value(streamer, 'is_live'),
            'last_updated': get_column_value(streamer, 'last_updated'),
        }
        
        # Instead of:
        # return {
        #     'id': streamer.id,  # mypy error: "Column" has no attribute "id"
        #     'username': streamer.username,  # same error
        #     # ...etc
        # }
    
    def list_streamers(self) -> List[Dict[str, Any]]:
        """List all streamers with proper typing"""
        streamers = self.db.query(Streamer).all()
        return [self.get_streamer_info(get_column_value(streamer, 'id')) for streamer in streamers]
