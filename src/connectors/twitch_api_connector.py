import requests
import time
import os
from typing import Dict, List, Optional, Tuple

class TwitchAPIConnector:
    """
    Handles connections to the Twitch Helix API to fetch game viewership data.
    Requires Client ID and Client Secret for authentication.
    """

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """
        Initialize the Twitch API connector.

        Args:
            client_id (str, optional): Twitch Application Client ID. Defaults to TWITCH_CLIENT_ID env var.
            client_secret (str, optional): Twitch Application Client Secret. Defaults to TWITCH_CLIENT_SECRET env var.
        """
        self.client_id = client_id or os.environ.get('TWITCH_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('TWITCH_CLIENT_SECRET')
        self.base_url = "https://api.twitch.tv/helix/"
        self.auth_url = "https://id.twitch.tv/oauth2/token"
        self._access_token: Optional[str] = None
        self._token_expiry_time: float = 0

        if not self.client_id or not self.client_secret:
            print("Warning: Twitch Client ID or Secret not provided. Authentication will fail.")

        # Rate limiting (placeholders, Twitch has specific limits)
        self.request_delay = 0.5 # Adjust based on Twitch limits (e.g., 800 points/min)
        self.last_request_time = 0

        # Request statistics
        self.request_count = 0
        self.error_count = 0
        # Cache for game_name -> game_id mapping
        self.game_id_cache: Dict[str, Optional[str]] = {}

    def _get_access_token(self) -> Optional[str]:
        """
        Obtains or refreshes the App Access Token from Twitch.
        """
        current_time = time.time()
        if self._access_token and current_time < self._token_expiry_time:
            return self._access_token

        if not self.client_id or not self.client_secret:
            print("Error: Cannot get access token without Client ID and Secret.")
            return None

        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        try:
            response = requests.post(self.auth_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get('access_token')
            # Set expiry time slightly earlier than actual expiry for safety
            self._token_expiry_time = current_time + data.get('expires_in', 3600) - 60
            print("Successfully obtained Twitch Access Token.")
            return self._access_token
        except requests.exceptions.RequestException as e:
            print(f"Error obtaining Twitch access token: {e}")
            self._access_token = None
            self._token_expiry_time = 0
            return None

    def _rate_limit_request(self):
        """Applies simple time-based rate limiting. Twitch has more complex point-based limits."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.request_delay:
            time.sleep(self.request_delay - time_since_last_request)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Makes an authenticated request to the Twitch Helix API.
        Handles token refresh, rate limiting, and basic error handling.
        """
        token = self._get_access_token()
        if not token:
            return None

        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {token}'
        }
        url = self.base_url + endpoint.lstrip('/')

        self._rate_limit_request()
        self.request_count += 1
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                # Check for 401/403 Unauthorized specifically for token issues
                if response.status_code in [401, 403]:
                     print("Warning: Received 401/403. Forcing token refresh.")
                     self._access_token = None # Force refresh on next call
                     token = self._get_access_token() # Try refreshing immediately
                     if not token: return None # Still failed
                     headers['Authorization'] = f'Bearer {token}' # Update header
                     # Retry the request immediately after potential refresh
                     response = requests.get(url, headers=headers, params=params, timeout=10)

                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                self.error_count += 1
                print(f"Error making Twitch API request to {url}: {e} (Status: {response.status_code if 'response' in locals() else 'N/A'})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return None # Failed after retries

    def get_game_id_by_name(self, game_name: str) -> Optional[str]:
        """
        Finds the Twitch Game ID for a given game name. Caches results.

        Args:
            game_name (str): The exact name of the game as known by Twitch.

        Returns:
            Optional[str]: The Twitch Game ID, or None if not found or an error occurs.
        """
        # Check cache first
        if game_name in self.game_id_cache:
            return self.game_id_cache[game_name]

        endpoint = "games"
        params = {'name': game_name}
        response = self._make_request(endpoint, params=params)

        game_id: Optional[str] = None # Default to None

        if response and response.get('data'):
            # Check if the data list is not empty
            if len(response['data']) > 0:
                 # Assuming the first result is the most relevant one
                game_data = response['data'][0]
                # --- Removed strict name check ---
                # # Verify the name matches closely (optional, Twitch often returns exact match first)
                # if game_data.get('name', '').lower() == game_name.lower():
                #     game_id = game_data.get('id')
                # else:
                #      print(f"Warning: Twitch returned '{game_data.get('name')}' for '{game_name}', ID not cached.")
                # --- End Removal ---
                # Trust the first result from the Twitch API
                game_id = game_data.get('id')
                # Optional: Log if the name is different, but still use the ID
                if game_data.get('name', '').lower() != game_name.lower():
                    print(f"Info: Twitch returned game '{game_data.get('name')}' (ID: {game_id}) for query '{game_name}'. Using this ID.")

            else:
                # Game name likely not found on Twitch
                print(f"Info: Game '{game_name}' not found on Twitch.")
        else:
            # Error occurred during API request or no data field
            print(f"Error: Failed to retrieve game ID for '{game_name}' from Twitch API.")
            # We cache None on error/not found to avoid retrying constantly
            # If you prefer retrying later, don't cache None here.

        # Cache the result (even if None)
        self.game_id_cache[game_name] = game_id
        return game_id

    def get_game_streams(self, game_id: str, first: int = 100) -> Optional[List[Dict]]:
        """
        Gets a list of active streams for a specific game ID.

        Args:
            game_id (str): The Twitch Game ID.
            first (int): Maximum number of streams to return (1-100). Defaults to 100.

        Returns:
            Optional[List[Dict]]: A list of stream objects, or None if an error occurs.
                                Each stream object contains details like user_id, user_name,
                                viewer_count, started_at, etc.
        """
        endpoint = "streams"
        # Ensure 'first' is within Twitch API limits (1-100)
        params = {
            'game_id': game_id,
            'first': max(1, min(first, 100))
        }

        response = self._make_request(endpoint, params=params)

        if response and 'data' in response:
            # Note: Twitch returns an empty list in 'data' if no streams are live,
            # which is valid, not an error.
            # Pagination handling ('pagination' key in response) is omitted for now.
            return response['data']
        elif response is None:
            # Error occurred during API request
            print(f"Error: Failed to retrieve streams for game ID '{game_id}' from Twitch API.")
            return None
        else:
            # Response received, but no 'data' key (unexpected format)
            print(f"Warning: Unexpected response format when retrieving streams for game ID '{game_id}'. Response: {response}")
            return None # Treat unexpected format as failure

    def get_game_viewership(self, game_id: str) -> Optional[int]:
        """
        Calculates the total concurrent viewers for a specific game ID.

        This currently sums viewers from the first page (up to 100 streams)
        returned by get_game_streams. For games with >100 streams, this
        will be an undercount unless pagination is implemented in get_game_streams.

        Args:
            game_id (str): The Twitch Game ID.

        Returns:
            Optional[int]: The total concurrent viewer count, or None if an error occurs
                           while fetching streams.
        """
        streams = self.get_game_streams(game_id, first=100) # Get first 100 streams

        if streams is not None:
            # streams can be an empty list if no one is streaming, sum will be 0
            total_viewers = sum(stream.get('viewer_count', 0) for stream in streams)
            return total_viewers
        else:
            # An error occurred in get_game_streams
            print(f"Error: Could not calculate viewership for game ID '{game_id}' due to stream fetch error.")
            return None

    def get_api_statistics(self) -> Dict:
        """Gets statistics about API usage."""
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        return {
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'error_rate_percent': error_rate,
            'cache_size': len(self.game_id_cache), # Updated cache reference
            'token_valid': self._access_token is not None and time.time() < self._token_expiry_time
        }

    def clear_cache(self) -> None:
        """Clears the internal game ID cache.""" # Updated docstring
        self.game_id_cache.clear() # Updated cache reference
        print("TwitchAPIConnector game ID cache cleared.")

# Example Usage (requires environment variables TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET)
# if __name__ == '__main__':
#     connector = TwitchAPIConnector()
#     # Need to implement get_game_id_by_name first
#     # game_id = connector.get_game_id_by_name("Apex Legends")
#     # if game_id:
#     #     viewers = connector.get_game_viewership(game_id)
#     #     if viewers is not None:
#     #         print(f"Current viewers for Apex Legends: {viewers}")
#     #     else:
#     #         print("Could not retrieve viewership.")
#     # else:
#     #     print("Could not find game ID.")
#     # print(connector.get_api_statistics())

