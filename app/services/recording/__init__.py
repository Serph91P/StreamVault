"""
Service initializer for the recording module.

This module defines the service's main entry points and exports.
"""
from .recording_service import RecordingService
from .config_manager import ConfigManager
from .process_manager import ProcessManager
from .recording_logger import RecordingLogger
from .exceptions import (
    RecordingError, ProcessError, ConfigurationError, 
    StreamUnavailableError, FileOperationError
)

__all__ = [
    'RecordingService', 
    'ConfigManager',
    'ProcessManager',
    'RecordingLogger',
    'RecordingError',
    'ProcessError',
    'ConfigurationError',
    'StreamUnavailableError',
    'FileOperationError'
]

# Main entry point function for starting the service
async def start_recording_service(db=None):
    """Start the recording service
    
    Args:
        db: Optional database session
    
    Returns:
        RecordingService instance that has been started
    """
    service = RecordingService(db=db)
    await service.start()
    
    # Start the state persistence service
    from app.services.state_persistence_service import state_persistence_service
    await state_persistence_service.start()
    
    # Start the new background queue service
    from app.services.startup_init import initialize_background_services
    await initialize_background_services()
    
    # Recover active recordings from persistent storage
    await service.recover_active_recordings_from_persistence()
    
    # Start the active recordings broadcaster
    from app.services.active_recordings_broadcaster import start_active_recordings_broadcaster
    await start_active_recordings_broadcaster(service)
    
    return service
