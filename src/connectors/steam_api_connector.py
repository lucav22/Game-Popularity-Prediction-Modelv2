"""
Steam API Connector Module

Purpose:
    Provides a robust interface for connecting to the Steam API with rate limiting,
    error handling, and caching mechanisms. This is a core component for real-time
    game data collection in the Game Popularity Prediction System v2.

Key Features:
    - Rate-limited API requests to prevent throttling
    - Error handling and retry logic
    - Caching mechanism to reduce redundant API calls
    - Methods for retrieving game details and player counts

Author: Gianluca Villegas
Date: 2025-04-27
Version: 2.0
"""

import requests
import time
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Tuple

class SteamAPIConnector:
    """
    A class to handle connections to the Steam API for retrieving game data.
    This implementation focuses on retrieving current and historical player counts.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Steam API connector.
        
        Args:
            api_key (str, optional): Steam API key. If None, will look for STEAM_API_KEY environment variable.
            
        Note:
            While public player count data doesn't strictly require an API key,
            having one is recommended for expanded functionality and higher rate limits.
        """
        self.api_key = api_key or os.environ.get('STEAM_API_KEY')
        
        # API endpoints
        self.base_url = "https://api.steampowered.com/"
        self.store_url = "https://store.steampowered.com/api/"
        
        # Rate limiting parameters
        self.request_delay = 1.0  # Seconds between requests
        self.last_request_time = 0
        
        # Cache for app details to avoid repeated lookups
        self.app_cache = {}
        
        # Request statistics
        self.request_count = 0
        self.error_count = 0
        
    def _rate_limit_request(self) -> None:
        """
        Apply rate limiting to API requests.
        
        This ensures we don't overwhelm the Steam API servers and risk getting blocked.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.request_delay:
            time.sleep(self.request_delay - time_since_last_request)
            
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        Make a request to the Steam API with rate limiting and error handling.
        
        Args:
            url (str): The URL to request
            params (Dict, optional): Query parameters
            
        Returns:
            Dict: JSON response from the API
            
        Note:
            This method implements exponential backoff for failed requests
            and maintains request statistics for monitoring.
        """
        self._rate_limit_request()
        self.request_count += 1
        
        max_retries = 3
        retry_delay = 1  # Initial retry delay in seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                self.error_count += 1
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"Error making request to {url}: {e}")
                    return {}
    
    def get_app_list(self) -> Dict:
        """
        Get a list of all games/applications on Steam.
        
        Returns:
            Dict: Raw API response containing app list
            
        Note:
            This method returns the raw response for flexibility.
            Consider implementing caching for this heavy operation.
        """
        url = f"{self.base_url}ISteamApps/GetAppList/v2/"
        return self._make_request(url)
    
    def get_app_details(self, app_id: int) -> Dict:
        """
        Get detailed information about a specific game.
        
        Args:
            app_id (int): The Steam application ID
            
        Returns:
            Dict: Detailed information about the game including:
                - Basic info (name, developer, publisher)
                - Release date
                - Price information
                - Genre classifications
                - Ratings and reviews
                
        Note:
            Results are cached to minimize API calls for repeated game lookups.
        """
        # Check cache first
        if app_id in self.app_cache:
            return self.app_cache[app_id]
        
        url = f"{self.store_url}appdetails/"
        params = {'appids': app_id}
        
        response = self._make_request(url, params)
        
        if response and str(app_id) in response:
            # Cache the result
            app_details = response[str(app_id)]
            self.app_cache[app_id] = app_details
            return app_details
        
        return {}
    
    def get_current_player_count(self, app_id: int) -> int:
        """
        Get the current number of players for a game.
        
        Args:
            app_id (int): The Steam application ID
            
        Returns:
            int: Current player count (0 if error)
            
        Note:
            This is one of the most frequently used methods and should be
            called efficiently to build time series data.
        """
        url = f"{self.base_url}ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
        params = {'appid': app_id}
        
        response = self._make_request(url, params)
        
        if response and 'response' in response and 'player_count' in response['response']:
            return response['response']['player_count']
        
        return 0
    
    def get_multiple_player_counts(self, app_ids: List[int]) -> Dict[int, int]:
        """
        Get current player counts for multiple games efficiently.
        
        Args:
            app_ids (List[int]): List of Steam application IDs
            
        Returns:
            Dict[int, int]: Mapping of app_id to player_count
            
        Note:
            This method implements batch processing for efficiency.
            Results include timestamp for tracking data collection time.
        """
        results = {}
        
        for app_id in app_ids:
            player_count = self.get_current_player_count(app_id)
            results[app_id] = player_count
            
        results['timestamp'] = datetime.now().isoformat()
        return results
    
    def get_api_statistics(self) -> Dict:
        """
        Get statistics about API usage.
        
        Returns:
            Dict: Statistics including request count, error count, and error rate
            
        Useful for:
            - Monitoring API performance
            - Detecting rate limiting issues
            - Optimizing request patterns
        """
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        
        return {
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'error_rate_percent': error_rate,
            'cache_size': len(self.app_cache)
        }
    
    def clear_cache(self) -> None:
        """
        Clear the application details cache.
        
        Useful when:
            - Memory usage becomes too high
            - App details need to be refreshed
            - Testing/debugging
        """
        self.app_cache.clear()