import os
import json
import getpass
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class CredentialManager:
    """Manages API credentials with caching and automatic refresh."""
    
    def __init__(self, cache_dir: str, service_name: str):
        """
        Initialize the credential manager.
        
        Args:
            cache_dir: Base directory for caching
            service_name: Name of the service (e.g., 'autorouter')
        """
        self.cache_dir = Path(cache_dir)
        self.service_name = service_name
        self.credential_file = self.cache_dir / f"{service_name}_credentials.json"
        self.credentials: Optional[Dict[str, Any]] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None

    def set_credentials(self, username: Optional[str] = None, password: Optional[str] = None) -> None:
        """
        Set credentials programmatically.
        
        Args:
            username: Username to use
            password: Password to use
        """
        self._username = username
        self._password = password

    def get_credentials(self) -> Dict[str, Any]:
        """
        Get credentials, refreshing if necessary.
        
        Returns:
            Dictionary containing credentials
        """
        if self.credentials is None:
            self._load_credentials()
            
        if self._is_expired():
            self._refresh_credentials()
            
        return self.credentials

    def _load_credentials(self) -> None:
        """Load credentials from cache file."""
        if self.credential_file.exists():
            with open(self.credential_file) as f:
                try:
                    self.credentials = json.load(f)
                except json.JSONDecodeError:
                    logger.error(f"Error parsing credentials file {self.credential_file}")
                    self.credentials = None

    def _is_expired(self) -> bool:
        """Check if credentials are expired."""
        if not self.credentials:
            return True
            
        exp = datetime.fromisoformat(self.credentials.get('expiration', '2000-01-01'))
        return exp < datetime.now()

    def _get_credentials_from_user(self) -> Tuple[str, str]:
        """
        Get credentials from user input or programmatic values.
        
        Returns:
            Tuple of (username, password)
        """
        username = self._username
        password = self._password
        
        if username is None:
            username = input('Username: ')
            
        if password is None:
            password = getpass.getpass()
            
        return username, password

    def _refresh_credentials(self) -> None:
        """Refresh credentials by asking user and making API call."""
        if self.credentials:
            logger.info(f"Token expired at {self.credentials['expiration']}")
            
        username, password = self._get_credentials_from_user()
        
        # This would be implemented by the specific service
        # For Autorouter, it would be:
        # response = requests.post('https://api.autorouter.aero/v1.0/oauth2/token',
        #     data={
        #         'client_id': username,
        #         'client_secret': password,
        #         'grant_type': 'client_credentials'
        #     }
        # )
        
        # For now, we'll just store the credentials
        self.credentials = {
            'username': username,
            'access_token': password,  # In reality, this would be the token from the API
            'expiration': (datetime.now() + timedelta(days=1)).isoformat()
        }
        
        self._save_credentials()

    def _save_credentials(self) -> None:
        """Save credentials to cache file."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.credential_file, 'w') as f:
            json.dump(self.credentials, f)

    def clear_credentials(self) -> None:
        """Clear cached credentials."""
        if self.credential_file.exists():
            os.remove(self.credential_file)
        self.credentials = None 