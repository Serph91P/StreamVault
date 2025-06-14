"""
Enhanced Recording Logger for StreamVault
Provides comprehensive logging for all recording activities
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

class RecordingActivityLogger:
    """Comprehensive logger for recording activities with context tracking"""
    
    def __init__(self):
        self.logger = logging.getLogger("streamvault.recording.activity")
        self.session_contexts = {}  # Track recording sessions
    
    def start_recording_session(self, streamer_id: int, streamer_name: str, context: Dict[str, Any]) -> str:
        """Start a new recording session with context tracking"""
        session_id = f"{streamer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.session_contexts[session_id] = {
            "streamer_id": streamer_id,
            "streamer_name": streamer_name,
            "start_time": datetime.now(),
            "context": context,
            "events": []
        }
        
        self.logger.info(f"[SESSION_START:{session_id}] {streamer_name} (ID: {streamer_id})")
        self.logger.info(f"[SESSION_START:{session_id}] Context: {json.dumps(context, indent=2)}")
        
        return session_id
    
    def log_session_event(self, session_id: str, event_type: str, details: str, level: str = "info"):
        """Log an event within a recording session"""
        if session_id in self.session_contexts:
            event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "details": details,
                "level": level
            }
            self.session_contexts[session_id]["events"].append(event)
            
            streamer_name = self.session_contexts[session_id]["streamer_name"]
            message = f"[{event_type}:{session_id}] {streamer_name} - {details}"
            
            if level == "debug":
                self.logger.debug(message)
            elif level == "warning":
                self.logger.warning(message)
            elif level == "error":
                self.logger.error(message)
            else:
                self.logger.info(message)
    
    def end_recording_session(self, session_id: str, reason: str = "completed"):
        """End a recording session and log summary"""
        if session_id in self.session_contexts:
            session = self.session_contexts[session_id]
            duration = (datetime.now() - session["start_time"]).total_seconds()
            
            self.logger.info(f"[SESSION_END:{session_id}] {session['streamer_name']} - Duration: {duration:.2f}s, Reason: {reason}")
            self.logger.info(f"[SESSION_END:{session_id}] Events: {len(session['events'])}")
            
            # Log session summary
            self._log_session_summary(session_id, session)
            
            # Clean up session context
            del self.session_contexts[session_id]
    
    def _log_session_summary(self, session_id: str, session: Dict[str, Any]):
        """Log a comprehensive session summary"""
        summary = {
            "session_id": session_id,
            "streamer_name": session["streamer_name"],
            "streamer_id": session["streamer_id"],
            "start_time": session["start_time"].isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - session["start_time"]).total_seconds(),
            "total_events": len(session["events"]),
            "context": session["context"],
            "events": session["events"]
        }
        
        self.logger.info(f"[SESSION_SUMMARY:{session_id}] {json.dumps(summary, indent=2)}")
    
    def log_process_lifecycle(self, process_type: str, streamer_name: str, action: str, details: Optional[Dict[str, Any]] = None):
        """Log process lifecycle events (start, monitor, stop)"""
        message = f"[PROCESS_{action.upper()}] {process_type} for {streamer_name}"
        if details:
            message += f" - {json.dumps(details)}"
        
        self.logger.info(message)
    
    def log_file_operation_detailed(self, operation: str, file_path: str, success: bool, 
                                   details: Optional[Dict[str, Any]] = None, performance_metrics: Optional[Dict[str, Any]] = None):
        """Log detailed file operations with performance metrics"""
        status = "SUCCESS" if success else "FAILED"
        
        # Get file size if file exists
        file_size_mb = 0
        if os.path.exists(file_path):
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        message = f"[FILE_OP_{status}] {operation}: {file_path} (Size: {file_size_mb:.2f} MB)"
        
        if details:
            message += f" - Details: {json.dumps(details)}"
        
        if performance_metrics:
            message += f" - Performance: {json.dumps(performance_metrics)}"
        
        if success:
            self.logger.info(message)
        else:
            self.logger.error(message)
    
    def log_configuration_impact(self, setting: str, old_value: Any, new_value: Any, 
                                streamer_id: Optional[int] = None, impact_analysis: Optional[str] = None):
        """Log configuration changes with impact analysis"""
        target = "Global" if streamer_id is None else f"Streamer {streamer_id}"
        
        message = f"[CONFIG_CHANGE] {target}: {setting} changed from '{old_value}' to '{new_value}'"
        if impact_analysis:
            message += f" - Impact: {impact_analysis}"
        
        self.logger.info(message)
    
    def log_error_with_context(self, error_type: str, streamer_name: str, error_message: str, 
                              context: Optional[Dict[str, Any]] = None, stack_trace: Optional[str] = None):
        """Log errors with rich context information"""
        message = f"[ERROR_{error_type}] {streamer_name}: {error_message}"
        
        if context:
            message += f" - Context: {json.dumps(context)}"
        
        self.logger.error(message)
        
        if stack_trace:
            self.logger.error(f"[ERROR_{error_type}_STACK] {streamer_name}: {stack_trace}")
    
    def log_performance_metrics(self, operation: str, streamer_name: str, metrics: Dict[str, Any]):
        """Log performance metrics for operations"""
        message = f"[PERFORMANCE] {operation} for {streamer_name}: {json.dumps(metrics)}"
        self.logger.info(message)
    
    def log_quality_metrics(self, streamer_name: str, file_path: str, quality_metrics: Dict[str, Any]):
        """Log recording quality metrics"""
        message = f"[QUALITY_METRICS] {streamer_name} ({file_path}): {json.dumps(quality_metrics)}"
        self.logger.info(message)
    
    def log_resource_usage(self, operation: str, resource_metrics: Dict[str, Any]):
        """Log system resource usage during operations"""
        message = f"[RESOURCE_USAGE] {operation}: {json.dumps(resource_metrics)}"
        self.logger.info(message)
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get information about currently active recording sessions"""
        return {
            session_id: {
                "streamer_name": session["streamer_name"],
                "streamer_id": session["streamer_id"],
                "start_time": session["start_time"].isoformat(),
                "duration_seconds": (datetime.now() - session["start_time"]).total_seconds(),
                "event_count": len(session["events"])
            }
            for session_id, session in self.session_contexts.items()
        }


# Global instance for easy access
recording_activity_logger = RecordingActivityLogger()
