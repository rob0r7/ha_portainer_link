import logging
import aiohttp
from typing import Optional, Dict, Any

_LOGGER = logging.getLogger(__name__)

class PortainerAuth:
    """Handle Portainer authentication."""

    def __init__(self, base_url: str, username: Optional[str] = None, 
                 password: Optional[str] = None, api_key: Optional[str] = None,
                 ssl_verify: bool = True):
        """Initialize authentication."""
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self.token: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers: Dict[str, str] = {}

    async def initialize(self, session: aiohttp.ClientSession) -> bool:
        """Initialize authentication with session."""
        self.session = session
        
        if self.api_key:
            self.headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            }
            _LOGGER.info("✅ Using API key authentication")
            return True
        elif self.username and self.password:
            return await self.authenticate()
        else:
            _LOGGER.error("❌ No credentials provided")
            return False

    async def authenticate(self) -> bool:
        """Authenticate with username/password."""
        if not self.session:
            _LOGGER.error("❌ Session not initialized")
            return False
            
        url = f"{self.base_url}/api/auth"
        payload = {"Username": self.username, "Password": self.password}
        
        try:
            async with self.session.post(url, json=payload, ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get("jwt")
                    self.headers = {
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    }
                    _LOGGER.info("✅ Authentication successful")
                    return True
                else:
                    _LOGGER.error("❌ Authentication failed: HTTP %s", resp.status)
                    return False
        except Exception as e:
            _LOGGER.exception("❌ Authentication error: %s", e)
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get current authentication headers."""
        return self.headers.copy()

    def is_authenticated(self) -> bool:
        """Check if authentication is valid."""
        return bool(self.headers and (self.token or self.api_key))

    async def close(self) -> None:
        """Close the authentication session."""
        if self.session:
            await self.session.close()
            self.session = None
