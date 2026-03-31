from slowapi import Limiter
from slowapi.util import get_remote_address

class RateLimiterConfig:
    def __init__(self):
        self.limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])
    
    def get_limiter(self) -> Limiter:
        return self.limiter
        
rate_limiter_config = RateLimiterConfig()
limiter = rate_limiter_config.get_limiter()