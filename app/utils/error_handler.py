"""
Centralized error handling utilities to prevent information exposure
"""
import logging
from fastapi import HTTPException
from typing import Optional

logger = logging.getLogger(__name__)

def handle_api_error(
    exception: Exception, 
    operation: str, 
    status_code: int = 500,
    public_message: Optional[str] = None
) -> HTTPException:
    """
    Handle API errors securely without exposing internal details
    
    Args:
        exception: The original exception
        operation: Description of what operation was being performed
        status_code: HTTP status code to return
        public_message: Safe message to show to users (optional)
    
    Returns:
        HTTPException: Safe exception to raise
    """
    # Log the full error details for developers
    logger.error(f"Error during {operation}: {exception}", exc_info=True)
    
    # Return a generic error message to users
    if public_message:
        detail = public_message
    else:
        detail = f"An error occurred while {operation}. Please contact support if the issue persists."
    
    return HTTPException(status_code=status_code, detail=detail)

def create_error_response(
    success: bool = False,
    message: str = "An error occurred",
    error_code: Optional[str] = None
) -> dict:
    """
    Create a standardized error response for non-HTTP endpoints
    
    Args:
        success: Whether the operation was successful
        message: User-friendly error message
        error_code: Optional error code for client handling
    
    Returns:
        dict: Standardized error response
    """
    response = {
        "success": success,
        "message": message
    }
    
    if error_code:
        response["error_code"] = error_code
    
    return response

# Common error messages
ERRORS = {
    "SUBSCRIPTION_FAILED": "Failed to subscribe to push notifications",
    "UNSUBSCRIPTION_FAILED": "Failed to unsubscribe from push notifications", 
    "NOTIFICATION_SEND_FAILED": "Failed to send notification",
    "CONFIG_RETRIEVAL_FAILED": "Failed to retrieve configuration",
    "CONFIG_UPDATE_FAILED": "Failed to update configuration",
    "RECORDING_START_FAILED": "Failed to start recording",
    "RECORDING_STOP_FAILED": "Failed to stop recording",
    "STREAM_RETRIEVAL_FAILED": "Failed to retrieve stream information",
    "STREAM_DELETE_FAILED": "Failed to delete stream",
    "STREAMER_RETRIEVAL_FAILED": "Failed to retrieve streamer information",
    "STREAMER_UPDATE_FAILED": "Failed to update streamer information",
    "DATABASE_ERROR": "A database error occurred",
    "AUTH_ERROR": "Authentication failed",
    "VALIDATION_ERROR": "Invalid request data",
    "NOT_FOUND": "The requested resource was not found",
    "PERMISSION_DENIED": "You don't have permission to perform this action",
    "SERVICE_UNAVAILABLE": "The service is temporarily unavailable"
}
