import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.controller import router as api_router
from src.api.limiter import limiter

class AppServer:
    def __init__(self):
        self._setup_logging()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ENV = os.getenv("ENV", "dev")
        
        self.app = FastAPI(
            title="CV Beautifier API",
            description="An API to enhance CVs using AI orchestration with Map-Reduce tailoring.",
            version="1.0.0",
            docs_url=None if self.ENV == "prod" else "/docs",
            redoc_url=None if self.ENV == "prod" else "/redoc",
            openapi_url=None if self.ENV == "prod" else "/openapi.json"
        )    
        
        self._configure_middlewares()
        self._configure_rate_limiter()
        self._configure_routes()
        
    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    
    def _configure_middlewares(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        
    def _configure_rate_limiter(self):
        self.app.state.limiter = limiter
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        
    def _configure_routes(self):
        self.app.include_router(api_router)
    
    def get_app(self) -> FastAPI:
        return self.app


# Instantiate the server and get the FastAPI app
server = AppServer()
app = server.get_app()

if __name__ == "__main__":
    import uvicorn
    server.logger.info("Starting CV Beautifier API server...")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)