#!/usr/bin/env python3
"""
Quick test script to validate Streamlink command formatting.
Run this to verify the OAuth token fix.
"""

import sys
sys.path.insert(0, '/home/maxe/Dokumente/private_projects/StreamVault')

from app.utils.streamlink_utils import get_streamlink_command

print("=" * 80)
print("Testing Streamlink Command Formatting")
print("=" * 80)

# Test 1: OAuth Token Format
print("\n1. Testing OAuth Token Format:")
print("-" * 80)
cmd = get_streamlink_command(
    streamer_name="test_streamer",
    quality="best",
    output_path="/tmp/test.ts",
    oauth_token="test_token_123abc"
)

oauth_found = False
for i, arg in enumerate(cmd):
    if "twitch-api-header" in arg:
        print(f"   Index {i}: {arg}")
        oauth_found = True
        
        # Check format
        if arg.startswith("--twitch-api-header="):
            print("   ✅ CORRECT: Single argument with =")
            if "Authorization=OAuth test_token_123abc" in arg:
                print("   ✅ CORRECT: Proper OAuth format")
        else:
            print("   ❌ WRONG: Split into multiple arguments")

if not oauth_found:
    print("   ⚠️  OAuth argument not found in command")

# Test 2: Codec Format
print("\n2. Testing Codec Format:")
print("-" * 80)
cmd = get_streamlink_command(
    streamer_name="test_streamer",
    quality="best",
    output_path="/tmp/test.ts",
    supported_codecs="h264,h265,av1"
)

codec_found = False
for i, arg in enumerate(cmd):
    if "twitch-supported-codecs" in arg:
        print(f"   Index {i}: {arg}")
        codec_found = True
        
        if arg.startswith("--twitch-supported-codecs="):
            print("   ✅ CORRECT: Single argument with =")
        else:
            print("   ❌ WRONG: Split into multiple arguments")

# Test 3: Proxy Format
print("\n3. Testing Proxy Format:")
print("-" * 80)
cmd = get_streamlink_command(
    streamer_name="test_streamer",
    quality="best",
    output_path="/tmp/test.ts",
    proxy_settings={
        "http": "http://user:pass@proxy.example.com:8080"
    }
)

proxy_found = False
for i, arg in enumerate(cmd):
    if "http-proxy" in arg:
        print(f"   Index {i}: {arg}")
        proxy_found = True
        
        if arg.startswith("--http-proxy="):
            print("   ✅ CORRECT: Single argument with =")
        else:
            print("   ❌ WRONG: Split into multiple arguments")

# Test 4: Full Command with All Options
print("\n4. Full Command Example:")
print("-" * 80)
cmd = get_streamlink_command(
    streamer_name="Dhalucard",
    quality="best",
    output_path="/recordings/test.ts",
    oauth_token="abcdefghijklmnopqrstuvwxyz0123",
    supported_codecs="h264,h265"
)

print("\nGenerated command:")
for i, arg in enumerate(cmd):
    if "twitch-api-header" in arg or "supported-codecs" in arg:
        print(f"  [{i}] {arg} ⭐")
    else:
        print(f"  [{i}] {arg}")

print("\n" + "=" * 80)
print("Test Complete!")
print("=" * 80)
