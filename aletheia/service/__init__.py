"""Local service layer for Aletheia."""

from aletheia.service.auth import AuthContext, AuthService
from aletheia.service.http import AletheiaDaemon, AletheiaService
from aletheia.service.mcp import McpToolRegistry

__all__ = ["AletheiaDaemon", "AletheiaService", "AuthContext", "AuthService", "McpToolRegistry"]
