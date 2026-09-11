# Railway/ASGI compatibility entrypoint
# The real FastAPI app lives in server.py.
from server import app

__all__ = ["app"]
