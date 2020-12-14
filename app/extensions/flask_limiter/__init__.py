# encoding: utf-8
"""
flask limiter
---------------
"""
# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
#
# from functools import wraps
# from flask import g, Blueprint, request
# from flask_limiter import Limiter, RateLimitExceeded
# from flask_limiter.util import get_remote_address
# from flask_limiter.wrappers import LimitGroup

from functools import wraps
from flask_login import current_user
from flask import request
from .exceptions import RateLimited
from .utils import is_rate_limited
from app.extensions.api import abort
from flask_restplus_patched._http import HTTPStatus


import logging
log = logging.getLogger(__name__)


"""
Decorator for request rate limit
Rate Example = 10/m, (m= minute), 1/s,(s= second), 40/h, (h=hour), 100/d, (d=day)
"""


def ratelimit(rate='100/s', redis_url='redis://redis:6379/0'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.modules import create_audit_trails, update_token_expiry_time
            #log.info(request.headers.get('X-Real-Ip'))
            current_path = request.path
            try:
                key = current_user.id

                action = request.method + "_" + str(current_path)
                #create_audit_trails(action)

                update_token_expiry_time(current_user.id)
            except:
                key = request.headers.get('X-Real-Ip') #current_user.id


            key = str(key)+'_'+str(current_path)+'_'+request.method
            message = "Too many requests."

            if 'validate_otp' in current_path or '/oauth2/token' in current_path:
                message = message +"Your account has been locked for 2 minutes."

            if is_rate_limited(rate, key, f, redis_url):
                abort(
                    code=HTTPStatus.TOO_MANY_REQUESTS,
                    message=message
                )
            return f(*args, **kwargs)

        return decorated_function

    return decorator