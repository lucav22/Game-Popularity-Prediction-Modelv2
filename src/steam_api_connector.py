import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import json
from typing import Dict, List, Optional, Union, Tuple

class SteamAPIConnector:
    """
    A class to handle connections to the Steam API for retrieving game data.
    This implementation focuses on retrieving current and historical player counts.
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the Steam API connector.
        
        Args:
            api_key (str, optional): Steam API key. If None, will look for STEAM_API_KEY environment variable.
        """
        # Note: For public player count data, an API key isn't strictly required,
        # but it's good practice to include for future expansion
        self.api_key = api_key or os.environ.get('STEAM_API_KEY')
        self.base_url = "https://api.steampowered.com/"
        self.store_url = "https://store.steampowered.com/api/"
        self.steam_charts_url = "https://steamcharts.com/app/"
        
        # Rate limiting parameters
        self.request_delay = 1.0  # Time in seconds to wait between requests
        self.last_request_time = 0
        
        # Cache for app details to avoid repeated lookups
        self.app_cache = {}
        
    def _rate_limit_request(self):
        """Apply rate limiting to API requests."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.request_delay:
            time.sleep(self.request_delay - time_since_last_request)
            
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Dict = None) -> Dict:
        """
        Make a request to the Steam API with rate limiting.
        
        Args:
            url (str): The URL to request
            params (Dict, optional): Query parameters
            
        Returns:
            Dict: JSON response from the API
        """
        self._rate_limit_request()
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            return {}
    
    def get_app_list(self) -> pd.DataFrame:
        """
        Get a list of all games/applications on Steam.
        
        Returns:
            pd.DataFrame: DataFrame containing app_id and name of all Steam applications
        """
        url = f"{self.base_url}ISteamApps/GetAppList/v2/"
        response = self._make_request(url)
        
        if not response or 'applist' not in response or 'apps' not in response['applist']:
            return pd.DataFrame(columns=['app_id', 'name'])
        
        apps = response['applist']['apps']
        return pd.DataFrame(apps)
    
    def get_app_details(self, app_id: int) -> Dict:
        """
        Get detailed information about a specific game.
        
        Args:
            app_id (int): The Steam application ID
            
        Returns:
            Dict: Detailed information about the game
        """
        # Check cache first
        if app_id in self.app_cache:
            return self.app_cache[app_id]
        
        url = f"{self.store_url}appdetails/"
        params = {'appids': app_id}
        
        response = self._make_request(url, params)
        
        if not response or str(app_id) not in response:
            return {}
        
        # Cache the result
        app_details = response[str(app_id)]
        self.app_cache[app_id] = app_details
        
        return app_details
    
    def get_current_player_count(self, app_id: int) -> int:
        """
        Get the current number of players for a game.
        
        Args:
            app_id (int): The Steam application ID
            
        Returns:
            int: Current player count
        """
        url = f"{self.base_url}ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
        params = {'appid': app_id}
        
        response = self._make_request(url, params)
        
        if not response or 'response' not in response or 'player_count' not in response['response']:
            return 0
        
        return response['response']['player_count']
    
    def get_historical_player_counts(self, app_id: int, start_date=None, end_date=None) -> pd.DataFrame:
        """
        Get historical player counts for a game.
        Note: Steam API doesn't officially provide historical data.
        This method would need to be supplemented with data from other sources
        or by building a database of daily snapshots.
        
        Args:
            app_id (int): The Steam application ID
            start_date: Optional start date for historical data
            end_date: Optional end date for historical data
            
        Returns:
            pd.DataFrame: DataFrame with historical player counts
        """
        # For now, return a placeholder message since Steam API doesn't provide this directly
        print(f"Note: Historical data for app_id {app_id} would need to be collected over time or from a third-party source.")
        
        # In a real implementation, you would either:
        # 1. Query your own database of historical snapshots
        # 2. Use web scraping for steamcharts.com (with permission)
        # 3. Use a third-party API that provides this data
        
        # Return an empty DataFrame with the expected structure
        return pd.DataFrame(columns=['datetime', 'player_count'])
    
    def get_game_data_batch(self, app_ids: List[int]) -> Dict[int, Dict]:
        """
        Get current player counts and basic info for multiple games.
        
        Args:
            app_ids (List[int]): List of Steam application IDs
            
        Returns:
            Dict[int, Dict]: Dictionary mapping app_ids to their data
        """
        results = {}
        
        for app_id in app_ids:
            # Get basic game info
            app_details = self.get_app_details(app_id)
            
            # Get current player count
            player_count = self.get_current_player_count(app_id)
            
            # Store both in results
            results[app_id] = {
                'details': app_details,
                'current_players': player_count,
                'timestamp': datetime.now().isoformat()
            }
            
        return results
    
    def save_data_to_csv(self, data: Dict[int, Dict], filename: str):
        """
        Save the collected game data to a CSV file.
        
        Args:
            data (Dict[int, Dict]): The game data to save
            filename (str): The name of the CSV file to save to
        """
        rows = []
        
        for app_id, app_data in data.items():
            row = {
                'app_id': app_id,
                'timestamp': app_data['timestamp'],
                'player_count': app_data['current_players']
            }
            
            # Add basic game details if available
            if app_data['details'] and 'data' in app_data['details']:
                game_data = app_data['details']['data']
                row['name'] = game_data.get('name', '')
                row['release_date'] = game_data.get('release_date', {}).get('date', '')
                row['metacritic_score'] = game_data.get('metacritic', {}).get('score', '')
                row['genres'] = ','.join([genre.get('description', '') for genre in game_data.get('genres', [])])
                
            rows.append(row)
            
        df = pd.DataFrame(rows)
        df.to_csv(filename, index=False)
        print(f"Data saved to {filename}")
        
    def build_player_history_dataset(self, app_ids: List[int], days_to_collect: int = 30) -> pd.DataFrame:
        """
        Simulate building a dataset of player history by collecting data daily.
        This is for demonstration purposes - in a real implementation, you would
        run this function on a schedule (e.g., daily) to build historical data.
        
        Args:
            app_ids (List[int]): List of Steam application IDs to track
            days_to_collect (int): Number of days to collect data
            
        Returns:
            pd.DataFrame: DataFrame with simulated historical player counts
        """
        print(f"In a real implementation, you would run a data collection script daily.")
        print(f"For demonstration, we'll collect current player counts for {len(app_ids)} games.")
        
        # Collect current data only (no historical simulation)
        all_data = []
        for app_id in app_ids:
            count = self.get_current_player_count(app_id)
            app_details = self.get_app_details(app_id)
            
            game_name = ""
            if app_details and 'data' in app_details:
                game_name = app_details['data'].get('name', f"App {app_id}")
                
            all_data.append({
                'app_id': app_id,
                'name': game_name,
                'player_count': count,
                'datetime': datetime.now().isoformat()
            })
            
        return pd.DataFrame(all_data)

# Example usage
if __name__ == "__main__":
    # List of example game IDs to track (CS:GO, Dota 2, PUBG, etc.)
    SAMPLE_GAME_IDS = [
        730,     # CS:GO
        570,     # Dota 2
        578080,  # PUBG
        1172470, # Apex Legends
        1599340, # Lost Ark
        1938090, # Call of Duty®: Modern Warfare® III | Warzone™
        1091500, # Cyberpunk 2077
        1675200  # Baldur's Gate 3
    ]
    
    # Initialize the connector
    steam_connector = SteamAPIConnector()
    
    # Get current player counts for the sample games
    print("Collecting current player data for sample games...")
    data = steam_connector.get_game_data_batch(SAMPLE_GAME_IDS)
    
    # Save the data to CSV
    steam_connector.save_data_to_csv(data, "current_steam_data.csv")
    
    # Example of how to build a historical dataset (in a real implementation)
    print("\nDemonstrating how to collect historical data (simulation only):")
    df = steam_connector.build_player_history_dataset(SAMPLE_GAME_IDS[:3], days_to_collect=3)
    print(df.head())