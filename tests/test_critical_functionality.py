#!/usr/bin/env python3
"""
Test critical functionality after refactoring
"""

def test_critical_services():
    """Test that critical services can be instantiated"""
    print("TESTING CRITICAL SERVICE INSTANTIATION")
    print("=" * 45)
    
    tests_passed = 0
    tests_total = 0
    
    # Test AuthService
    tests_total += 1
    try:
        from app.services.core.auth_service import AuthService
        from app.database import SessionLocal
        db = SessionLocal()
        auth_service = AuthService(db)
        db.close()
        print("  OK: AuthService instantiation")
        tests_passed += 1
    except Exception as e:
        print(f"  FAIL: AuthService: {e}")
    
    # Test RecordingService
    tests_total += 1
    try:
        from app.services.recording.recording_service import RecordingService
        print("  OK: RecordingService import")
        tests_passed += 1
    except Exception as e:
        print(f"  FAIL: RecordingService: {e}")
    
    # Test NotificationService
    tests_total += 1
    try:
        from app.services.notification_service import NotificationService
        print("  OK: NotificationService import")
        tests_passed += 1
    except Exception as e:
        print(f"  FAIL: NotificationService: {e}")
        
    # Test StreamerService
    tests_total += 1
    try:
        from app.services.streamer_service import StreamerService
        print("  OK: StreamerService import")
        tests_passed += 1
    except Exception as e:
        print(f"  FAIL: StreamerService: {e}")
        
    # Test UnifiedImageService
    tests_total += 1
    try:
        from app.services.unified_image_service import unified_image_service
        print("  OK: UnifiedImageService import")
        tests_passed += 1
    except Exception as e:
        print(f"  FAIL: UnifiedImageService: {e}")
    
    print(f"\nCRITICAL SERVICES: {tests_passed}/{tests_total} passed")
    return tests_passed == tests_total

if __name__ == "__main__":
    success = test_critical_services()
    print("CRITICAL FUNCTIONALITY:", "PASS" if success else "FAIL")
