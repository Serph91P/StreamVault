"""
Stream information handling and detection.

This module handles stream information detection and management.
"""
import logging
import asyncio
import json
from typing import Dict, Optional, Any, List, Tuple

from app.models import Stream

# Import any existing utilities
from app.utils.streamlink_utils import get_streamlink_version, get_stream_info

logger = logging.getLogger("streamvault")

class StreamInfoManager:
    """Manager for handling stream information and detection"""
    
    def __init__(self, config_manager=None):
        """Initialize the stream information manager
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.cache_timeout = 60  # Default 60 seconds
        self.stream_info_cache = {}  # Cache for stream info
        
    async def get_stream_info(self, stream: Stream, force_refresh: bool = False) -> Dict[str, Any]:
        """Get stream information using Streamlink
        
        Args:
            stream: Stream model object
            force_refresh: Force refresh the stream info cache
            
        Returns:
            Dictionary with stream information
        """
        # Check cache first if not forcing refresh
        if not force_refresh:
            cached_info = self._get_cached_stream_info(stream.id)
            if cached_info:
                return cached_info
        
        try:
            logger.info(f"Detecting stream info for {stream.name}")
            
            # Use existing utils to get stream info
            stream_url = stream.url
            custom_options = json.loads(stream.streamlink_options) if stream.streamlink_options else {}
            
            # Use custom proxy if configured
            proxy_settings = self._get_proxy_settings()
            
            # Set timeout from config or use default
            timeout = self._get_timeout_value()
            
            # Get stream information
            result = await get_stream_info(
                url=stream_url,
                options=custom_options,
                proxy=proxy_settings.get('http') if proxy_settings else None,
                timeout=timeout
            )
            
            if result and 'streams' in result:
                # Store in cache
                self._cache_stream_info(stream.id, result)
                return result
            else:
                logger.warning(f"No stream info found for {stream.name}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting stream info for {stream.name}: {e}", exc_info=True)
            return {}
    
    async def check_stream_online(self, stream: Stream) -> Tuple[bool, Dict[str, Any]]:
        """Check if a stream is online
        
        Args:
            stream: Stream model object
            
        Returns:
            Tuple of (is_online, stream_info)
        """
        try:
            stream_info = await self.get_stream_info(stream)
            
            if stream_info and 'streams' in stream_info and stream_info['streams']:
                return True, stream_info
            
            return False, stream_info
            
        except Exception as e:
            logger.error(f"Error checking if stream {stream.name} is online: {e}", exc_info=True)
            return False, {}
    
    async def get_best_quality(self, stream: Stream) -> Optional[str]:
        """Get the best quality for a stream
        
        Args:
            stream: Stream model object
            
        Returns:
            Best quality name or None if no stream info available
        """
        stream_info = await self.get_stream_info(stream)
        
        if not stream_info or 'streams' not in stream_info or not stream_info['streams']:
            return None
        
        # Check if the quality preference exists in the config
        preferred_quality = self._get_preferred_quality()
        
        # First try to match preferred quality if specified
        if preferred_quality and preferred_quality in stream_info['streams']:
            return preferred_quality
        
        # Then try to use best quality
        if 'best' in stream_info['streams']:
            return 'best'
        
        # Otherwise, choose the first available quality
        available_qualities = list(stream_info['streams'].keys())
        if available_qualities:
            return available_qualities[0]
            
        return None
    
    def _cache_stream_info(self, stream_id: int, stream_info: Dict[str, Any]) -> None:
        """Cache stream information
        
        Args:
            stream_id: Stream ID
            stream_info: Stream information to cache
        """
        self.stream_info_cache[stream_id] = {
            'timestamp': asyncio.get_event_loop().time(),
            'data': stream_info
        }
    
    def _get_cached_stream_info(self, stream_id: int) -> Optional[Dict[str, Any]]:
        """Get cached stream information if valid
        
        Args:
            stream_id: Stream ID
            
        Returns:
            Cached stream info or None if not found or expired
        """
        if stream_id not in self.stream_info_cache:
            return None
            
        cache_entry = self.stream_info_cache[stream_id]
        current_time = asyncio.get_event_loop().time()
        
        # Check if cache is still valid
        if current_time - cache_entry['timestamp'] < self.cache_timeout:
            return cache_entry['data']
            
        # Cache expired
        return None
        
    def _get_timeout_value(self) -> int:
        """Get timeout value from config
        
        Returns:
            Timeout in seconds
        """
        if self.config_manager:
            return self.config_manager.get_config_value("streamlink_timeout", default=30)
        return 30  # Default timeout
        
    def _get_proxy_settings(self) -> Optional[Dict[str, str]]:
        """Get proxy settings from config
        
        Returns:
            Dictionary with proxy settings or None if not configured
        """
        if self.config_manager:
            http_proxy = self.config_manager.get_config_value("http_proxy", default=None)
            https_proxy = self.config_manager.get_config_value("https_proxy", default=None)
            
            if http_proxy or https_proxy:
                proxies = {}
                if http_proxy:
                    proxies['http'] = http_proxy
                if https_proxy:
                    proxies['https'] = https_proxy
                return proxies
                
        return None
        
    def _get_preferred_quality(self) -> Optional[str]:
        """Get preferred quality from config
        
        Returns:
            Preferred quality or None if not configured
        """
        if self.config_manager:
            return self.config_manager.get_config_value("preferred_quality", default=None)
        return None
