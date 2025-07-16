#!/usr/bin/env python3
"""
Test script to validate all refactored services import correctly
"""

import sys
import traceback

# Test all refactored services by category
service_tests = {
    "Core Services": [
        "app.services.core.auth_service",
        "app.services.core.test_service",
    ],
    "API Services": [
        "app.services.api.twitch_oauth_service",
    ],
    "Processing Services": [
        "app.services.processing.task_dependency_manager",
        "app.services.processing.post_processing_tasks",
        "app.services.processing.post_processing_task_handlers",
    ],
    "System Services": [
        "app.services.system.logging_service",
        "app.services.system.cleanup_service", 
        "app.services.system.migration_service",
        "app.services.system.system_config_service",
    ],
    "Media Services": [
        "app.services.media.metadata_service",
        "app.services.media.thumbnail_service",
        "app.services.media.artwork_service",
    ],
    "Communication Services": [
        "app.services.communication.websocket_manager",
        "app.services.communication.enhanced_push_service",
    ],
    "Image Services": [
        "app.services.images.image_sync_service",
    ],
    "Recording Services": [
        "app.services.recording.recording_service",
        "app.services.recording.recording_orchestrator",
        "app.services.recording.recording_state_manager",
        "app.services.recording.recording_database_service",
        "app.services.recording.recording_websocket_service",
        "app.services.recording.post_processing_coordinator",
    ],
    "Queue Services": [
        "app.services.queues.task_queue_manager",
        "app.services.queues.task_progress_tracker",
        "app.services.queues.worker_manager",
    ],
    "Init Services": [
        "app.services.init.background_queue_init",
        "app.services.init.startup_init",
    ],
    "Main Services": [
        "app.services.notification_service",
        "app.services.streamer_service",
        "app.services.unified_image_service",
        "app.services.background_queue_service",
    ]
}

def test_service_imports():
    """Test all service imports"""
    total_tests = 0
    passed_tests = 0
    failed_services = []
    
    print("TESTING REFACTORED SERVICES IMPORTS")
    print("=" * 50)
    
    for category, services in service_tests.items():
        print(f"\n[{category}]:")
        
        for service in services:
            total_tests += 1
            try:
                __import__(service)
                print(f"  OK: {service}")
                passed_tests += 1
            except Exception as e:
                print(f"  FAIL: {service}: {str(e)[:80]}...")
                failed_services.append((service, str(e)))
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed_tests}/{total_tests} services passed")
    
    if failed_services:
        print(f"\nFAILED SERVICES ({len(failed_services)}):")
        for service, error in failed_services:
            print(f"  - {service}: {error[:100]}...")
        return False
    else:
        print("ALL SERVICES IMPORT SUCCESSFULLY!")
        return True

if __name__ == "__main__":
    success = test_service_imports()
    sys.exit(0 if success else 1)
