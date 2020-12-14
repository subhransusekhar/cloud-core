from functools import wraps

from .exceptions import RateLimited
from .utils import is_rate_limited


def ratelimit(rate, key, redis_url='redis://redis:6379/0'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if is_rate_limited(rate, key, f, redis_url):
                raise RateLimited("Too Many Requests")
            return f(*args, **kwargs)
        return decorated_function
    return decorator
