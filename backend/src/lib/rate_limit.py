"""Rate-limiting infrastructure via slowapi.

Per ADR-0001 and PHASE-02 Decision D-1:
- Key function uses ONLY direct TCP connection IP (get_remote_address)
- NO X-Forwarded-For header parsing or trust-proxy logic
- Conservative default: all browser-proxied traffic shares one coarser rate-limit bucket
"""

from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)
