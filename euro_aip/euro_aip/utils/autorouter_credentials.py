import requests
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from .credentials import CredentialManager

logger = logging.getLogger(__name__)

class AutorouterCredentialManager(CredentialManager):
    """Credential manager specifically for Autorouter API."""
    
    def __init__(self, cache_dir: str):
        """
        Initialize the Autorouter credential manager.
        
        Args:
            cache_dir: Base directory for caching
        """
        super().__init__(cache_dir, 'autorouter')
        self.token_url = 'https://api.autorouter.aero/v1.0/oauth2/token'

    def _refresh_credentials(self) -> None:
        """Refresh credentials by asking user and making API call."""
        if self.credentials:
            logger.info(f"Token expired at {self.credentials['expiration']}")
            
        username, password = self._get_credentials_from_user()
        
        try:
            response = requests.post(
                self.token_url,
                data={
                    'client_id': username,
                    'client_secret': password,
                    'grant_type': 'client_credentials'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.credentials = {
                    'username': username,
                    'access_token': data['access_token'],
                    'expiration': (datetime.now() + timedelta(seconds=data['expires_in'])).isoformat()
                }
                self._save_credentials()
                logger.info("Successfully obtained new token")
            else:
                logger.error(f'Error {response.status_code} retrieving token: {response.text}')
                raise ValueError(f"Failed to get token: {response.text}")
        except requests.RequestException as e:
            logger.error(f"Error connecting to Autorouter API: {e}")
            raise

    def get_token(self) -> str:
        """
        Get the current access token, refreshing if necessary.
        
        Returns:
            Current access token
        """
        credentials = self.get_credentials()
        return credentials['access_token'] 