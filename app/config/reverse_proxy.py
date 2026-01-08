"""
Reverse Proxy Detection and Configuration

This module handles automatic detection of reverse proxy setups
and configures security settings accordingly.
"""

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger("streamvault")


class ReverseProxyDetector:
    """Detects reverse proxy configuration and adjusts security settings"""

    PROXY_HEADERS = [
        'HTTP_X_FORWARDED_PROTO',
        'HTTP_X_FORWARDED_SSL',
        'HTTP_X_FORWARDED_HOST',
        'HTTP_X_REAL_IP',
        'HTTP_X_FORWARDED_FOR',
        'HTTP_CF_CONNECTING_IP',  # Cloudflare
        'HTTP_X_ORIGINAL_FORWARDED_FOR'  # AWS ALB
    ]

    @classmethod
    def is_behind_proxy(cls) -> bool:
        """Check if the application is behind a reverse proxy"""
        return any(os.getenv(header) for header in cls.PROXY_HEADERS)

    @classmethod
    def is_https_terminated(cls) -> bool:
        """Check if HTTPS is terminated at the reverse proxy"""
        forwarded_proto = os.getenv('HTTP_X_FORWARDED_PROTO', '').lower()
        forwarded_ssl = os.getenv('HTTP_X_FORWARDED_SSL', '').lower()

        return (
            forwarded_proto == 'https'
            or forwarded_ssl in ['on', '1', 'true']
            or os.getenv('HTTPS', '').lower() in ['on', '1', 'true']
        )

    @classmethod
    def get_proxy_info(cls) -> Dict[str, Optional[str]]:
        """Get detailed proxy information for debugging"""
        return {
            'x_forwarded_proto': os.getenv('HTTP_X_FORWARDED_PROTO'),
            'x_forwarded_ssl': os.getenv('HTTP_X_FORWARDED_SSL'),
            'x_forwarded_host': os.getenv('HTTP_X_FORWARDED_HOST'),
            'x_real_ip': os.getenv('HTTP_X_REAL_IP'),
            'x_forwarded_for': os.getenv('HTTP_X_FORWARDED_FOR'),
            'cf_connecting_ip': os.getenv('HTTP_CF_CONNECTING_IP'),
            'is_behind_proxy': cls.is_behind_proxy(),
            'is_https_terminated': cls.is_https_terminated()
        }

    @classmethod
    def should_use_secure_cookies(cls, default_secure: bool = True) -> bool:
        """
        Determine if secure cookies should be used based on proxy configuration

        Args:
            default_secure: Default value when not behind a proxy

        Returns:
            True if secure cookies should be used, False otherwise
        """
        # Environment override
        env_secure = os.getenv('USE_SECURE_COOKIES', '').lower()
        if env_secure in ['true', '1', 'on']:
            return True
        elif env_secure in ['false', '0', 'off']:
            return False

        # Auto-detect based on proxy
        if cls.is_behind_proxy():
            return cls.is_https_terminated()

        # Default for direct access
        return default_secure
