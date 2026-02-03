#!/usr/bin/env python3
"""
Test script to validate all API routes import correctly
"""

import sys

# Test all API routes
route_modules = [
    "app.routes.videos",
    "app.routes.streamers",
    "app.routes.recording",
    "app.routes.categories",
    "app.routes.settings",
    "app.routes.auth",
    "app.routes.push",
    "app.routes.logging",
    "app.routes.images",
    "app.routes.api_images",
    "app.routes.background_queue",
    "app.routes.admin",
    "app.routes.twitch_auth",
    "app.api.background_queue_endpoints",
]


def test_route_imports():
    """Test all route imports"""
    total_tests = 0
    passed_tests = 0
    failed_routes = []

    print("TESTING API ROUTES IMPORTS")
    print("=" * 40)

    for route_module in route_modules:
        total_tests += 1
        try:
            __import__(route_module)
            print(f"  OK: {route_module}")
            passed_tests += 1
        except Exception as e:
            print(f"  FAIL: {route_module}: {str(e)[:80]}...")
            failed_routes.append((route_module, str(e)))

    print("\n" + "=" * 40)
    print(f"RESULTS: {passed_tests}/{total_tests} routes passed")

    if failed_routes:
        print(f"\nFAILED ROUTES ({len(failed_routes)}):")
        for route, error in failed_routes:
            print(f"  - {route}: {error[:100]}...")
        assert False, f"Failed to import {len(failed_routes)} routes"
    else:
        print("ALL ROUTES IMPORT SUCCESSFULLY!")
        assert True


if __name__ == "__main__":
    success = test_route_imports()
    sys.exit(0 if success else 1)
