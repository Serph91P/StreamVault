#!/usr/bin/env python3
"""
Test script to generate and print streamlink commands for debugging
"""
import os
import sys
import argparse
import json
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.utils.streamlink_utils import (
    get_streamlink_command,
    get_streamlink_vod_command,
    get_streamlink_clip_command,
    get_proxy_settings_from_db
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Generate and print streamlink commands based on arguments"""
    parser = argparse.ArgumentParser(description='Generate streamlink commands for testing')
    parser.add_argument('--type', choices=['stream', 'vod', 'clip'], default='stream',
                      help='Type of command to generate')
    parser.add_argument('--streamer', help='Streamer name (for stream commands)')
    parser.add_argument('--vod-id', help='VOD ID (for vod commands)')
    parser.add_argument('--clip-url', help='Clip URL (for clip commands)')
    parser.add_argument('--quality', default='best', help='Stream quality (default: best)')
    parser.add_argument('--output', default='./test_output.mp4', help='Output path')
    parser.add_argument('--force', action='store_true', help='Use force mode')
    parser.add_argument('--proxy', action='store_true', help='Include proxy settings from DB')
    parser.add_argument('--custom-proxy', help='Custom proxy in format http://host:port')
    
    args = parser.parse_args()
    
    # Set up proxy settings
    proxy_settings = {}
    if args.proxy:
        try:
            proxy_settings = get_proxy_settings_from_db()
            logger.info(f"Using proxy settings from database: {proxy_settings}")
        except Exception as e:
            logger.error(f"Failed to get proxy settings from database: {e}")
    
    if args.custom_proxy:
        proxy_settings = {"http": args.custom_proxy, "https": args.custom_proxy}
        logger.info(f"Using custom proxy: {args.custom_proxy}")
    
    # Generate the appropriate command based on the type
    if args.type == 'stream':
        if not args.streamer:
            logger.error("--streamer is required for stream commands")
            return 1
            
        cmd = get_streamlink_command(
            streamer_name=args.streamer,
            quality=args.quality,
            output_path=args.output,
            proxy_settings=proxy_settings if proxy_settings else None,
            force_mode=args.force
        )
        
    elif args.type == 'vod':
        if not args.vod_id:
            logger.error("--vod-id is required for vod commands")
            return 1
            
        cmd = get_streamlink_vod_command(
            video_id=args.vod_id,
            quality=args.quality,
            output_path=args.output,
            proxy_settings=proxy_settings if proxy_settings else None,
            force_mode=args.force
        )
        
    elif args.type == 'clip':
        if not args.clip_url:
            logger.error("--clip-url is required for clip commands")
            return 1
            
        cmd = get_streamlink_clip_command(
            clip_url=args.clip_url,
            quality=args.quality,
            output_path=args.output,
            proxy_settings=proxy_settings if proxy_settings else None
        )
    
    # Print the command
    logger.info("\nGenerated Streamlink Command:")
    print(" \\\n  ".join(cmd))
    
    # Print in a format suitable for copying to a shell
    logger.info("\nCommand for shell:")
    print(" ".join(cmd))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
