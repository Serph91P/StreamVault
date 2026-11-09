"""Local liveness probe using the configured public Host without external I/O."""

from http.client import HTTPConnection
import os
from urllib.parse import urlsplit


def main() -> int:
    host = urlsplit(os.environ.get("BASE_URL", "http://localhost:7000")).netloc
    connection = HTTPConnection("127.0.0.1", 7000, timeout=5)
    try:
        connection.request("GET", "/api/health/live", headers={"Host": host})
        return 0 if connection.getresponse().status == 200 else 1
    except OSError:
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
