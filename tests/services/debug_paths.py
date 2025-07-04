#!/usr/bin/env python3
"""
Debug script to check if frontend files exist in the expected locations
"""
import os
import sys

def check_file(path, description):
    exists = os.path.exists(path)
    print(f"{'✅' if exists else '❌'} {description}: {path}")
    if exists and os.path.isdir(path):
        try:
            files = os.listdir(path)
            print(f"    📁 Contents: {files[:5]}{'...' if len(files) > 5 else ''}")
        except:
            pass
    return exists

def main():
    print("🔍 Checking frontend build paths...\n")
    
    # Check various possible locations for index.html
    paths_to_check = [
        ("Current dir frontend dist", "app/frontend/dist/index.html"),
        ("Docker frontend dist", "/app/app/frontend/dist/index.html"),
        ("Alternative path", "frontend/dist/index.html"),
        ("Current dir frontend dist dir", "app/frontend/dist/"),
        ("Docker frontend dist dir", "/app/app/frontend/dist/"),
        ("Current dir assets", "app/frontend/dist/assets/"),
        ("Docker assets", "/app/app/frontend/dist/assets/"),
        ("Frontend src", "app/frontend/src/"),
        ("Frontend public", "app/frontend/public/"),
    ]
    
    found_index = False
    for desc, path in paths_to_check:
        if check_file(path, desc):
            if path.endswith("index.html"):
                found_index = True
    
    print(f"\n{'✅' if found_index else '❌'} Found usable index.html: {found_index}")
    
    # Check if we're in Docker
    in_docker = os.path.exists("/.dockerenv")
    print(f"🐳 Running in Docker: {in_docker}")
    
    # Check current working directory
    print(f"📍 Current working directory: {os.getcwd()}")
    
    # Check if frontend was built
    package_json_exists = os.path.exists("app/frontend/package.json")
    print(f"📦 Frontend package.json exists: {package_json_exists}")

if __name__ == "__main__":
    main()
