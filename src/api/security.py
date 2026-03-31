import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class AuthGuard:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bearer_token = HTTPBearer()
        self.secret_token = os.getenv("API_SECRET_TOKEN", "default-secret-token-dev-123")
        
    def verify(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
        if credentials.credentials != self.secret_token:
            self.logger.warning("Unauthorized access attempt with token: %s", credentials.credentials)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return credentials.credentials
    
auth_guard = AuthGuard()