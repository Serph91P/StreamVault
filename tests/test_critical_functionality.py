#!/usr/bin/env python3
"""
Test critical functionality after refactoring
Run this to validate core backend systems
"""
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_critical_services():
    """Test that critical services can be instantiated"""
    print("\n" + "="*60)
    print("TESTING CRITICAL SERVICE INSTANTIATION")
    print("="*60 + "\n")
    
    tests_passed = 0
    tests_total = 0
    errors = []
    
    # Test AuthService
    tests_total += 1
    try:
        from app.services.core.auth_service import AuthService
        from app.database import SessionLocal
        db = SessionLocal()
        auth_service = AuthService(db)
        db.close()
        print("  ✅ AuthService instantiation")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ AuthService: {e}")
        errors.append(f"AuthService: {e}")
    
    # Test RecordingService
    tests_total += 1
    try:
        from app.services.recording.recording_service import RecordingService
        service = RecordingService()
        print("  ✅ RecordingService import")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ RecordingService: {e}")
        errors.append(f"RecordingService: {e}")
    
    # Test NotificationService
    tests_total += 1
    try:
        from app.services.notification_service import NotificationService
        service = NotificationService()
        print("  ✅ NotificationService import")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ NotificationService: {e}")
        errors.append(f"NotificationService: {e}")
        
    # Test StreamerService
    tests_total += 1
    try:
        from app.services.streamer_service import StreamerService
        print("  ✅ StreamerService import")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ StreamerService: {e}")
        errors.append(f"StreamerService: {e}")
        
    # Test UnifiedImageService
    tests_total += 1
    try:
        from app.services.unified_image_service import unified_image_service
        print("  ✅ UnifiedImageService import")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ UnifiedImageService: {e}")
        errors.append(f"UnifiedImageService: {e}")
    
    # Test Database Connection
    tests_total += 1
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        print("  ✅ Database connection")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Database: {e}")
        errors.append(f"Database: {e}")
    
    # Test Background Queue
    tests_total += 1
    try:
        from app.services.processing.background_queue_service import background_queue
        stats = background_queue.get_queue_stats()
        print(f"  ✅ Background queue ({stats.get('total_active_tasks', 0)} tasks)")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Background queue: {e}")
        errors.append(f"Background queue: {e}")
    
    # Test Settings
    tests_total += 1
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        assert hasattr(settings, 'RECORDING_DIRECTORY'), "RECORDING_DIRECTORY missing"
        print(f"  ✅ Settings (RECORDING_DIRECTORY: {settings.RECORDING_DIRECTORY})")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Settings: {e}")
        errors.append(f"Settings: {e}")
    
    print(f"\n{'='*60}")
    print(f"CRITICAL SERVICES: {tests_passed}/{tests_total} passed")
    print(f"{'='*60}\n")
    
    if errors:
        print("❌ ERRORS:")
        for error in errors:
            print(f"  - {error}")
        print()
    
    return tests_passed == tests_total

if __name__ == "__main__":
    try:
        success = test_critical_services()
        print(f"{'='*60}")
        print(f"RESULT: {'✅ PASS' if success else '❌ FAIL'}")
        print(f"{'='*60}\n")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
