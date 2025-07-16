"""
Stream information handling and detection.

This module handles stream information from Twitch webhooks and database.
Since stream online status comes from Twitch EventSub webhooks, this manager
focuses on extracting metadata from database records.
"""
import logging
from typing import Dict, Optional, Any, List

from app.models import Stream, Streamer

logger = logging.getLogger("streamvault")

class StreamInfoManager:
    """Manager for handling stream information from webhooks and database"""
    
    def __init__(self, config_manager=None):
        """Initialize the stream information manager
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        
    async def get_stream_metadata(self, stream: Stream) -> Dict[str, Any]:
        """Get detailed stream metadata from database record
        
        Args:
            stream: Stream model object (populated by webhook)
            
        Returns:
            Dictionary with stream metadata
        """
        try:
            metadata = {
                'streamer_name': stream.streamer.username,
                'twitch_id': stream.streamer.twitch_id,
                'stream_title': stream.title,
                'category_name': stream.category_name,
                'language': stream.language,
                'started_at': stream.started_at.isoformat() if stream.started_at else None,
                'twitch_stream_id': stream.twitch_stream_id
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting stream metadata for {stream.streamer.username}: {e}", exc_info=True)
            return {
                'streamer_name': stream.streamer.username if stream.streamer else 'unknown',
                'error': str(e)
            }

    def get_preferred_quality(self) -> str:
        """Get preferred quality from config
        
        Returns:
            Preferred quality setting
        """
        if self.config_manager:
            return self.config_manager.get_config_value("preferred_quality", default="best")
        return "best"  # Default to best quality
        
    def get_quality_priority_list(self) -> List[str]:
        """Get the quality priority list for fallback selection
        
        Returns:
            List of qualities in priority order
        """
        return [
            'source', 'best', '1080p60', '1080p', '720p60', '720p', 
            '480p', '360p', 'worst'
        ]
