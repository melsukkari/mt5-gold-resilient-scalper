"""
Web module initialization.
"""

from .auth import auth_bp
from .routes import web_bp

__all__ = ["auth_bp", "web_bp"]
