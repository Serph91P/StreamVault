#!/usr/bin/env python3
"""
Test application startup sequence
"""

import sys
import os

def test_application_startup():
    """Test that the FastAPI application can be created"""
    print("TESTING APPLICATION STARTUP")
    print("=" * 35)
    
    try:
        # Import the FastAPI app
        from app.main import app
        print("  OK: FastAPI app import")
        
        # Check that app is created
        if app is not None:
            print("  OK: FastAPI app created")
        else:
            print("  FAIL: FastAPI app is None")
            return False
            
        # Check routes are registered
        routes = len(app.routes)
        if routes > 0:
            print(f"  OK: {routes} routes registered")
        else:
            print("  FAIL: No routes registered")
            return False
            
        print("\nAPPLICATION STARTUP: SUCCESS!")
        return True
        
    except Exception as e:
        print(f"  FAIL: Application startup failed: {e}")
        return False

if __name__ == "__main__":
    success = test_application_startup()
    sys.exit(0 if success else 1)
