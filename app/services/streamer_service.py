"""
StreamerService - Backward compatibility wrapper

This is a lightweight wrapper around the refactored streamer services
to maintain backward compatibility while the codebase migrates to the new structure.

Original God Class (347 lines) split into:
- StreamerRepository: Database operations for streamers, streams, settings
- TwitchIntegrationService: Twitch API calls and EventSub management
- StreamerImageService: Profile image downloading and caching
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.models import Streamer
from app.schemas.streamers import StreamerResponse
from app.services.communication.websocket_manager import ConnectionManager
from app.events.handler_registry import EventHandlerRegistry
from app.services.streamers import StreamerRepository, TwitchIntegrationService
from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")


class StreamerService:
    """Backward compatibility wrapper for the refactored streamer services"""
    
    def __init__(self, db: Session, websocket_manager: ConnectionManager, event_registry: EventHandlerRegistry):
        self.db = db
        self.manager = websocket_manager
        self.event_registry = event_registry
        
        # Initialize the refactored services
        self.repository = StreamerRepository(db)
        self.twitch_service = TwitchIntegrationService(event_registry)
        self.image_service = unified_image_service
        
        # Legacy properties for compatibility
        self.twitch_api = self.twitch_service.twitch_api

    async def notify(self, message: Dict[str, Any]):
        """Send WebSocket notification"""
        try:
            await self.manager.send_notification(message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            raise

    # Delegate methods to TwitchIntegrationService
    async def get_users_by_login(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Get users by login names"""
        return await self.twitch_service.get_users_by_login(usernames)

    async def get_streamer_info(self, streamer_id: str) -> Optional[Dict[str, Any]]:
        """Get streamer info by Twitch ID"""
        return await self.twitch_service.get_streamer_info(streamer_id)

    async def get_user_data(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user data from Twitch API"""
        return await self.twitch_service.get_user_data(username)

    async def get_stream_info(self, twitch_id: str) -> Optional[Dict[str, Any]]:
        """Get current stream information"""
        return await self.twitch_service.get_stream_info(twitch_id)

    async def check_streamer_live_status(self, twitch_id: str) -> bool:
        """Check if a specific streamer is currently live via Twitch API"""
        try:
            stream_info = await self.twitch_service.get_stream_info(twitch_id)
            return stream_info is not None
        except Exception as e:
            logger.error(f"Error checking live status for {twitch_id}: {e}")
            return False

    async def get_game_data(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Fetch game data from Twitch API"""
        return await self.twitch_service.get_game_data(game_id)

    async def subscribe_to_events(self, twitch_id: str):
        """Subscribe to EventSub events"""
        await self.twitch_service.subscribe_to_events(twitch_id)

    # Delegate methods to StreamerRepository
    async def get_streamers(self) -> List[StreamerResponse]:
        """Get all streamers with their current status"""
        return self.repository.get_all_streamers()

    async def get_streamer_by_username(self, username: str) -> Optional[Streamer]:
        """Get streamer by username"""
        return self.repository.get_streamer_by_username(username)

    # Delegate methods to UnifiedImageService
    async def download_profile_image(self, url: str, streamer_id: str) -> str:
        """Download and cache profile image"""
        result = await self.image_service.download_profile_image(int(streamer_id), url)
        return result or url

    # Combined methods that use multiple services
    async def add_streamer(self, username: str, display_name: str = None) -> Optional[Streamer]:
        """Add a new streamer with full setup"""
        try:
            logger.debug(f"Adding streamer: {username}")
            
            # Get user data from Twitch
            user_data = await self.twitch_service.get_user_data(username)
            if not user_data:
                logger.error(f"Could not fetch user data for {username}")
                return None
            
            logger.debug(f"User data retrieved: {user_data}")
            
            # Check if streamer already exists
            existing = self.repository.get_streamer_by_twitch_id(user_data['id'])
            if existing:
                logger.debug(f"Streamer already exists: {username}")
                return existing
            
            # Cache profile image
            cached_image_path = await self.image_service.download_profile_image(
                int(user_data['id']),
                user_data['profile_image_url']
            )
            
            # Check if streamer is currently live
            stream_info = None
            try:
                stream_info = await self.twitch_service.get_stream_info(user_data['id'])
                if stream_info:
                    logger.info(f"Streamer {username} is currently live: {stream_info.get('title', '')}")
                else:
                    logger.debug(f"Streamer {username} is currently offline")
            except Exception as e:
                logger.warning(f"Could not check live status for {username}: {e}")
            
            # Create new streamer using repository
            new_streamer = self.repository.create_streamer(
                user_data=user_data,
                display_name=display_name,
                cached_image_path=cached_image_path or user_data['profile_image_url'],
                stream_info=stream_info
            )
            
            # Subscribe to EventSub events
            try:
                await self.twitch_service.subscribe_to_events(user_data['id'])
            except Exception as e:
                logger.error(f"Failed to subscribe to EventSub events: {e}")
                # Don't fail the whole operation if EventSub subscription fails
            
            # Send notification about new streamer
            await self.notify({
                "type": "success",
                "message": f"Added streamer {new_streamer.username}"
            })
            
            return new_streamer
            
        except Exception as e:
            logger.error(f"Error adding streamer: {e}", exc_info=True)
            raise

    async def delete_streamer(self, streamer_id: int) -> Optional[Dict[str, Any]]:
        """Delete a streamer and cleanup"""
        try:
            # Get streamer data before deletion for EventSub cleanup
            streamer = self.repository.get_streamer_by_id(streamer_id)
            if not streamer:
                return None
            
            # Unsubscribe from EventSub events
            try:
                await self.twitch_service.unsubscribe_from_events(streamer.twitch_id)
            except Exception as e:
                logger.warning(f"Could not unsubscribe from EventSub events: {e}")
            
            # Delete from database
            streamer_data = self.repository.delete_streamer(streamer_id)
            
            if streamer_data:
                await self.notify({
                    "type": "success",
                    "message": f"Removed streamer {streamer_data['username']}"
                })
            
            return streamer_data
            
        except Exception as e:
            logger.error(f"Error deleting streamer: {e}", exc_info=True)
            raise

    # Additional convenience methods
    async def refresh_streamer_data(self, streamer_id: int) -> bool:
        """Refresh streamer data from Twitch API"""
        try:
            streamer = self.repository.get_streamer_by_id(streamer_id)
            if not streamer:
                return False
            
            # Get fresh data from Twitch
            user_data = await self.twitch_service.refresh_user_data(streamer.twitch_id)
            if not user_data:
                return False
            
            # Update profile image if changed
            if user_data.get('profile_image_url') != streamer.original_profile_image_url:
                cached_path = await self.image_service.update_streamer_profile_image(
                    streamer.id, user_data['profile_image_url']
                )
                if cached_path:
                    user_data['cached_profile_image'] = self.image_service.get_cached_profile_image(streamer.id)
            
            # Update streamer in database
            self.repository.update_streamer(
                streamer,
                username=user_data.get('display_name', streamer.username),
                profile_image_url=user_data.get('cached_profile_image', user_data.get('profile_image_url')),
                original_profile_image_url=user_data.get('profile_image_url')
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing streamer data for {streamer_id}: {e}")
            return False

    async def bulk_check_live_status(self, streamer_ids: List[int] = None) -> Dict[int, bool]:
        """Check live status for multiple streamers efficiently"""
        try:
            if streamer_ids:
                streamers = [self.repository.get_streamer_by_id(sid) for sid in streamer_ids]
                streamers = [s for s in streamers if s]  # Filter out None values
            else:
                # Get all streamers
                streamer_responses = self.repository.get_all_streamers()
                streamers = [self.repository.get_streamer_by_id(sr.id) for sr in streamer_responses]
                streamers = [s for s in streamers if s]
            
            if not streamers:
                return {}
            
            # Get Twitch IDs
            twitch_ids = [s.twitch_id for s in streamers]
            
            # Check status in bulk
            live_status = await self.twitch_service.check_stream_status_bulk(twitch_ids)
            
            # Map back to streamer IDs
            result = {}
            for streamer in streamers:
                result[streamer.id] = live_status.get(streamer.twitch_id, False)
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking bulk live status: {e}")
            return {}

    async def get_all_streamers(self) -> List[Streamer]:
        """Get all streamers from the database"""
        try:
            return self.repository.get_all_streamers_raw()
        except Exception as e:
            logger.error(f"Error getting all streamers: {e}")
            return []

    async def close(self):
        """Close all services"""
        try:
            await self.image_service.close()
        except Exception as e:
            logger.error(f"Error closing streamer service: {e}")
