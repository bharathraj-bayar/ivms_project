import json
from typing import Any
from config import Config
import redis
import os

_r = redis.Redis(host=os.getenv('REDIS_HOST', Config.REDIS_HOST), port=int(os.getenv('REDIS_PORT', Config.REDIS_PORT)), db=1, decode_responses=True)

def _key(tenant: str, prefix: str, key: str, version: int = 1):
    return f"ivms:cache:{tenant}:{prefix}:{version}:{key}"

def get_cache(tenant: str, prefix: str, key: str, version: int = 1):
    k = _key(tenant, prefix, key, version)
    v = _r.get(k)
    if not v:
        return None
    try:
        return json.loads(v)
    except Exception:
        return v

def set_cache(tenant: str, prefix: str, key: str, value: Any, ttl: int = 300, version: int = 1):
    k = _key(tenant, prefix, key, version)
    val = json.dumps(value)
    _r.setex(k, ttl, val)

def invalidate_cache(tenant: str, prefix: str, key: str = None, version: int = 1):
    if key:
        k = _key(tenant, prefix, key, version)
        _r.delete(k)
    else:
        pattern = f"ivms:cache:{tenant}:{prefix}:{version}:*"
        for k in _r.scan_iter(match=pattern):
            _r.delete(k)
