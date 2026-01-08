"""
Proxy URL Helper - Ensures proxy URLs are correctly URL-encoded

Handles special characters in usernames and passwords that need to be URL-encoded
for proper HTTP proxy authentication.
"""

from urllib.parse import urlparse, quote, urlunparse


def encode_proxy_url(proxy_url: str) -> str:
    """
    Ensure proxy URL has properly URL-encoded credentials.

    Problem: Passwords with special characters (_-@:/) must be URL-encoded.
    Example: eden11_Gigs → eden11%5FGigs

    Args:
        proxy_url: Proxy URL (http://user:pass@host:port)

    Returns:
        URL-encoded proxy URL

    Examples:
        >>> encode_proxy_url("http://user:pass_word@host:8080")
        'http://user:pass%5Fword@host:8080'

        >>> encode_proxy_url("http://user:already%5Fencoded@host:8080")
        'http://user:already%5Fencoded@host:8080'
    """
    # Parse URL
    parsed = urlparse(proxy_url)

    # Extract username and password from netloc
    if '@' not in parsed.netloc:
        # No credentials - return as-is
        return proxy_url

    # Split credentials and host
    credentials, host = parsed.netloc.rsplit('@', 1)

    # Check if already encoded (contains %)
    if '%' in credentials:
        # Already encoded - return as-is
        return proxy_url

    # Split username and password
    if ':' in credentials:
        username, password = credentials.split(':', 1)
    else:
        username = credentials
        password = ''

    # URL-encode both username and password
    # safe='' means encode everything including @ : / etc
    encoded_username = quote(username, safe='')
    encoded_password = quote(password, safe='') if password else ''

    # Rebuild netloc
    if encoded_password:
        encoded_netloc = f"{encoded_username}:{encoded_password}@{host}"
    else:
        encoded_netloc = f"{encoded_username}@{host}"

    # Rebuild full URL
    encoded_url = urlunparse((
        parsed.scheme,
        encoded_netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))

    return encoded_url


def decode_proxy_url_for_display(proxy_url: str) -> str:
    """
    Decode proxy URL for human-readable display.

    Args:
        proxy_url: URL-encoded proxy URL

    Returns:
        Human-readable proxy URL

    Examples:
        >>> decode_proxy_url_for_display("http://user:pass%5Fword@host:8080")
        'http://user:pass_word@host:8080'
    """
    from urllib.parse import unquote

    parsed = urlparse(proxy_url)

    if '@' not in parsed.netloc:
        return proxy_url

    credentials, host = parsed.netloc.rsplit('@', 1)

    # Decode credentials
    decoded_credentials = unquote(credentials)

    # Rebuild netloc
    decoded_netloc = f"{decoded_credentials}@{host}"

    # Rebuild URL
    decoded_url = urlunparse((
        parsed.scheme,
        decoded_netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))

    return decoded_url


if __name__ == "__main__":
    # Test cases
    test_urls = [
        "http://user:pass@host:8080",
        "http://user:already%5Fencoded@host:8080",
        "http://user:p@ss:word@host:8080",  # Multiple colons
        "http://no-auth@host:8080",  # No password
    ]

    print("Proxy URL Encoding Test")
    print("=" * 80)

    for url in test_urls:
        encoded = encode_proxy_url(url)
        decoded = decode_proxy_url_for_display(encoded)

        print(f"\nOriginal: {url}")
        print(f"Encoded:  {encoded}")
        print(f"Decoded:  {decoded}")
        print(f"Match: {'✅' if decoded == url or url.startswith('http://user:already') else '❌'}")
