import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import time
import json
import sys
from typing import List, Dict, Optional, Union, Tuple

# Import our custom Steam API connector
from steam_api_connector import SteamAPIConnector

class SteamDataCollector:
    """
    A class to handle the collection and management of Steam game data
    for the Game Popularity Prediction Model.
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the data collector.
        
        Args:
            data_dir (str): Directory to store collected data
        """
        self.data_dir = data_dir
        self.api = SteamAPIConnector()
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Define game categories (can be expanded)
        self.game_categories = {
            "successful": [
                730,    # CS:GO
                570,    # Dota 2
                578080, # PUBG
                1172470, # Apex Legends
                1599340, # Lost Ark
                1091500, # Cyberpunk 2077
                1675200  # Baldur's Gate 3
            ],
            "declining": [
                1240440, # Babylon's Fall
                1262900, # New World 
                594650,  # Hunt: Showdown
                235960,  # Natural Selection 2
                233860,  # Kenshi
                292030   # The Witcher 3: Wild Hunt
            ],
            "experimental": [
                1938090, # Call of Duty: Modern Warfare III | Warzone
                1551360, # Forza Horizon 5
                1245620, # ELDEN RING
                1063730, # New World
                1426210, # Constant Caliber
                1240520  # Redfall
            ]
        }
        
        # Store for collected data
        self.collected_data = {}
        
    def get_game_ids_by_category(self, category: Optional[str] = None) -> List[int]:
        """
        Get game IDs for a specific category or all categories.
        
        Args:
            category (str, optional): Category to get games for. If None, returns all games.
            
        Returns:
            List[int]: List of game IDs
        """
        if category and category in self.game_categories:
            return self.game_categories[category]
        else:
            # Return all game IDs from all categories
            all_ids = []
            for cat_ids in self.game_categories.values():
                all_ids.extend(cat_ids)
            return all_ids
            
    def collect_current_data(self, game_ids: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Collect current player data for specified games.
        
        Args:
            game_ids (List[int], optional): List of game IDs to collect data for.
                If None, collects data for all defined games.
                
        Returns:
            pd.DataFrame: DataFrame with collected data
        """
        # If no game IDs provided, use all defined games
        if game_ids is None:
            game_ids = self.get_game_ids_by_category()
            
        print(f"Collecting current player data for {len(game_ids)} games...")
        
        # Get data batch from API
        data = self.api.get_game_data_batch(game_ids)
        
        # Transform to DataFrame
        rows = []
        for app_id, app_data in data.items():
            row = {
                'app_id': app_id,
                'timestamp': app_data['timestamp'],
                'player_count': app_data['current_players']
            }
            
            # Add category information
            for category, ids in self.game_categories.items():
                if app_id in ids:
                    row['category'] = category
                    break
            else:
                row['category'] = 'uncategorized'
            
            # Add basic game details if available
            if app_data['details'] and 'data' in app_data['details']:
                game_data = app_data['details']['data']
                row['name'] = game_data.get('name', '')
                row['release_date'] = game_data.get('release_date', {}).get('date', '')
                row['metacritic_score'] = game_data.get('metacritic', {}).get('score', '')
                row['genres'] = ','.join([genre.get('description', '') for genre in game_data.get('genres', [])])
                row['is_free'] = game_data.get('is_free', False)
                
                # Extract price information if available
                price_info = game_data.get('price_overview', {})
                row['price'] = price_info.get('final_formatted', '') if price_info else ''
                
            rows.append(row)
            
        df = pd.DataFrame(rows)
        
        # Store the collected data
        self.collected_data[datetime.now().strftime('%Y-%m-%d-%H-%M')] = df
        
        return df
    
    def save_current_data(self, data: Optional[pd.DataFrame] = None, 
                         filename: Optional[str] = None) -> str:
        """
        Save the most recently collected data to a CSV file.
        
        Args:
            data (pd.DataFrame, optional): DataFrame to save. If None, uses the most recent data.
            filename (str, optional): Filename to save to. If None, generates a timestamped filename.
            
        Returns:
            str: Path to the saved file
        """
        # Use provided data or most recent collection
        if data is None:
            if not self.collected_data:
                raise ValueError("No data has been collected yet.")
            latest_key = max(self.collected_data.keys())
            data = self.collected_data[latest_key]
            
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
            filename = f"steam_data_{timestamp}.csv"
            
        # Ensure path is in data directory
        filepath = os.path.join(self.data_dir, filename)
        
        # Save data
        data.to_csv(filepath, index=False)
        print(f"Data saved to {filepath}")
        
        return filepath
    
    def load_data(self, filepath: str) -> pd.DataFrame:
        """
        Load data from a CSV file.
        
        Args:
            filepath (str): Path to the CSV file
            
        Returns:
            pd.DataFrame: Loaded data
        """
        # Handle relative paths
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.data_dir, filepath)
            
        # Check if file exists
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
            
        # Load data
        df = pd.DataFrame()
        try:
            df = pd.read_csv(filepath)
            print(f"Loaded data from {filepath}")
        except Exception as e:
            print(f"Error loading data from {filepath}: {e}")
            
        return df
    
    def setup_scheduled_collection(self, interval_hours: int = 24, 
                                  days_to_run: int = 30) -> None:
        """
        Set up scheduled data collection.
        Note: This is a simplified version for demonstration. In production,
        you would use a proper scheduler like cron or Airflow.
        
        Args:
            interval_hours (int): Hours between collections
            days_to_run (int): Number of days to run collections
        """
        print(f"Setting up scheduled collection every {interval_hours} hours for {days_to_run} days.")
        print("Note: In a production environment, you would use a proper scheduler.")
        print("For example, with cron or Airflow.")
        print("\nSimulated collection schedule:")
        
        start_time = datetime.now()
        for i in range(days_to_run * 24 // interval_hours):
            collection_time = start_time + timedelta(hours=i * interval_hours)
            print(f"  Collection {i+1}: {collection_time.strftime('%Y-%m-%d %H:%M')}")
            
        print("\nTo implement actual scheduled collection:")
        print("1. Use a task scheduler (cron, Airflow, etc.)")
        print("2. Set up a database for storing time series data")
        print("3. Include error handling and notification systems")
            
    def merge_historical_files(self, file_pattern: str = "steam_data_*.csv") -> pd.DataFrame:
        """
        Merge multiple historical data files into a single DataFrame.
        
        Args:
            file_pattern (str): Pattern to match historical data files
            
        Returns:
            pd.DataFrame: Merged historical data
        """
        import glob
        
        # Find all matching files
        file_paths = glob.glob(os.path.join(self.data_dir, file_pattern))
        
        if not file_paths:
            print(f"No files found matching pattern: {file_pattern}")
            return pd.DataFrame()
            
        print(f"Found {len(file_paths)} data files to merge.")
        
        # Load and merge all files
        dfs = []
        for file_path in file_paths:
            try:
                df = pd.read_csv(file_path)
                # Make sure timestamp is in the data
                if 'timestamp' not in df.columns:
                    # Extract timestamp from filename as fallback
                    timestamp_str = os.path.basename(file_path).replace('steam_data_', '').replace('.csv', '')
                    df['timestamp'] = timestamp_str
                    
                dfs.append(df)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                
        if not dfs:
            print("No valid data files could be loaded.")
            return pd.DataFrame()
            
        # Concatenate all dataframes
        merged_df = pd.concat(dfs, ignore_index=True)
        
        # Ensure timestamp is in datetime format
        try:
            merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'])
        except:
            print("Warning: Could not convert timestamp to datetime.")
            
        print(f"Merged data contains {len(merged_df)} records.")
        return merged_df
        
    def analyze_data_snapshot(self, data: Optional[pd.DataFrame] = None) -> Dict:
        """
        Perform basic analysis on a data snapshot.
        
        Args:
            data (pd.DataFrame, optional): Data to analyze. If None, uses the most recent data.
            
        Returns:
            Dict: Analysis results
        """
        # Use provided data or most recent collection
        if data is None:
            if not self.collected_data:
                raise ValueError("No data has been collected yet.")
            latest_key = max(self.collected_data.keys())
            data = self.collected_data[latest_key]
            
        # Basic analysis
        results = {
            'total_games': len(data),
            'timestamp': datetime.now().isoformat(),
            'category_counts': data['category'].value_counts().to_dict() if 'category' in data.columns else {},
            'total_players': data['player_count'].sum() if 'player_count' in data.columns else 0,
            'top_games': data.nlargest(5, 'player_count')[['name', 'player_count']].to_dict('records') 
                        if 'player_count' in data.columns and 'name' in data.columns else []
        }
        
        return results

# Example usage
if __name__ == "__main__":
    # Initialize the collector
    collector = SteamDataCollector()
    
    # Collect current data for all defined games
    current_data = collector.collect_current_data()
    
    # Save the data
    collector.save_current_data()
    
    # Perform basic analysis
    analysis = collector.analyze_data_snapshot(current_data)
    print("\nBasic Analysis:")
    for key, value in analysis.items():
        if key != 'top_games':
            print(f"  {key}: {value}")
            
    print("\nTop Games by Player Count:")
    for game in analysis['top_games']:
        print(f"  {game['name']}: {game['player_count']} players")