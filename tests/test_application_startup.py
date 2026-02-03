#!/usr/bin/env python3
"""
Test application startup sequence
"""

import sys


def test_application_startup():
    """Test that the FastAPI application can be created"""
    print("TESTING APPLICATION STARTUP")
    print("=" * 35)

    try:
        # Import the FastAPI app
        from app.main import app

        print("  OK: FastAPI app import")

        # Check that app is created
        assert app is not None, "FastAPI app is None"
        print("  OK: FastAPI app created")

        # Check routes are registered
        routes = len(app.routes)
        assert routes > 0, "No routes registered"
        print(f"  OK: {routes} routes registered")

        print("\nAPPLICATION STARTUP: SUCCESS!")

    except Exception as e:
        assert False, f"Application startup failed: {e}"


if __name__ == "__main__":
    success = test_application_startup()
    sys.exit(0 if success else 1)
