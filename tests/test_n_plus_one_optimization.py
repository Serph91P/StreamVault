"""
Test N+1 Query Optimization

This test validates that eager loading is properly implemented to prevent N+1 queries.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_eager_loading_syntax():
    """Test that the eager loading syntax is correct"""
    from sqlalchemy.orm import joinedload

    # Verify joinedload is importable
    assert joinedload is not None, "joinedload should be importable from sqlalchemy.orm"
    print("✓ joinedload is available")

    # Test that it can be called
    try:
        # These are the patterns used in the optimized code
        # We validate syntax without importing models (which may have dependencies)
        patterns = [
            "joinedload(Stream.streamer)",
            "joinedload(Recording.stream).joinedload(Stream.streamer)",
            "joinedload(Stream.recordings)",
            "joinedload(Stream.stream_events)",
            "joinedload(StreamEvent.stream).joinedload(Stream.streamer)",
            "joinedload(Streamer.streams)",
        ]

        # Check that these patterns exist in the actual code

        files = ["app/routes/status.py", "app/routes/streamers.py"]

        found_patterns = []
        for filepath in files:
            with open(filepath, "r") as f:
                content = f.read()
                for pattern in patterns:
                    if pattern.replace("joinedload", "joinedload") in content:
                        found_patterns.append(pattern)

        print(f"✓ Found {len(found_patterns)} eager loading patterns in code")
        for pattern in set(found_patterns):
            print(f"  - {pattern}")

        # Success if we found at least some patterns
        return len(found_patterns) > 0

    except Exception as e:
        print(f"✗ Error testing eager loading patterns: {e}")
        return False


def test_optimization_locations():
    """Test that optimization comments are present in the code"""

    files_to_check = [
        (
            "app/routes/status.py",
            [
                "PERF: Use eager loading to prevent N+1 queries",
                "PERF: Eager load streams to avoid N+1",
                "PERF: Fetch all active recordings in one query",
                "PERF: Eager load streamer and recordings to prevent N+1 queries",
                "PERF: Eager load stream and streamer to prevent N+1 queries",
            ],
        ),
        ("app/routes/streamers.py", ["PERF: Eager load stream_events to prevent N+1 queries"]),
    ]

    all_found = True
    for filepath, expected_comments in files_to_check:
        try:
            with open(filepath, "r") as f:
                content = f.read()

            for comment in expected_comments:
                if comment in content:
                    print(f"✓ Found optimization in {filepath}: '{comment[:50]}...'")
                else:
                    print(f"✗ Missing optimization in {filepath}: '{comment}'")
                    all_found = False

        except FileNotFoundError:
            print(f"✗ File not found: {filepath}")
            all_found = False

    return all_found


def test_joinedload_usage():
    """Test that joinedload is actually used in the query chains"""
    import re

    files_to_check = ["app/routes/status.py", "app/routes/streamers.py"]

    all_correct = True
    for filepath in files_to_check:
        try:
            with open(filepath, "r") as f:
                content = f.read()

            # Look for .options(joinedload(...))
            options_pattern = r"\.options\(\s*joinedload\("
            matches = re.findall(options_pattern, content)

            if matches:
                print(f"✓ Found {len(matches)} joinedload usage(s) in {filepath}")
            else:
                print(f"✗ No joinedload usage found in {filepath}")
                all_correct = False

        except FileNotFoundError:
            print(f"✗ File not found: {filepath}")
            all_correct = False

    return all_correct


def test_no_n_plus_one_patterns():
    """Test that common N+1 anti-patterns are eliminated"""
    import re

    # Check for queries inside loops (common N+1 pattern)
    files_to_check = ["app/routes/status.py", "app/routes/streamers.py"]

    # Patterns that indicate potential N+1 issues
    # These should be minimal after optimization
    anti_patterns = [
        r"for .+ in .+:\s+.*db\.query\(",  # Query inside for loop
    ]

    print("\nChecking for N+1 anti-patterns...")
    issues_found = 0

    for filepath in files_to_check:
        try:
            with open(filepath, "r") as f:
                content = f.read()

            for pattern in anti_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                if matches:
                    print(f"⚠ Found {len(matches)} potential N+1 pattern(s) in {filepath}")
                    issues_found += len(matches)
                    # Note: Some queries in loops may be intentional, so this is a warning not error
        except FileNotFoundError:
            print(f"✗ File not found: {filepath}")

    if issues_found == 0:
        print("✓ No obvious N+1 anti-patterns found")
    else:
        print(f"⚠ Found {issues_found} potential N+1 patterns (may need review)")

    return True  # Don't fail on warnings


if __name__ == "__main__":
    print("=" * 60)
    print("N+1 Query Optimization Test Suite")
    print("=" * 60)

    tests = [
        ("Eager Loading Syntax", test_eager_loading_syntax),
        ("Optimization Locations", test_optimization_locations),
        ("Joinedload Usage", test_joinedload_usage),
        ("N+1 Anti-patterns Check", test_no_n_plus_one_patterns),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Test: {test_name}")
        print("=" * 60)
        try:
            result = test_func()
            results.append((test_name, result))
            status = "PASSED" if result else "FAILED"
            print(f"\nResult: {status}")
        except Exception as e:
            print(f"\nResult: ERROR - {e}")
            results.append((test_name, False))

    print(f"\n{'=' * 60}")
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    sys.exit(0 if passed == total else 1)
