"""
Data Collector Module

Purpose:
    Manages the collection, storage, and organization of game data from various sources.
    This module provides the infrastructure for building time series datasets of game
    popularity metrics for the Game Popularity Prediction System v2.

Key Features:
    - Categorized game tracking (successful, declining, experimental)
    - Data collection scheduling and automation
    - CSV storage with compression options
    - Data merging and aggregation capabilities

Author: Gianluca Villegas
Date: 2025-05-04
Version: 2.0
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
from typing import List, Dict, Optional, Union, Tuple
from pathlib import Path

from src.connectors.steam_api_connector import SteamAPIConnector

class DataCollector:
    """
    A class to handle the collection and management of game data for predictive modeling.
    
    This collector is designed to be extensible to multiple data sources beyond Steam.
    """
    
    def __init__(self, data_dir: str = "data", config_path: Optional[str] = None):
        """
        Initialize the data collector.
        
        Args:
            data_dir (str): Directory to store collected data
            config_path (str, optional): Path to configuration file
            
        The configuration file should contain:
            - Game categories and their IDs
            - Collection schedules
            - API credentials
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize API connector
        self.steam_api = SteamAPIConnector()
        
        # Load or initialize game categories
        self.config_path = config_path
        self.game_categories = self._load_game_categories()
        
        # Create storage for collected data
        self.collected_data = {}
        
    def _load_game_categories(self) -> Dict[str, List[int]]:
        """
        Load game categories from config file or use defaults.
        
        Returns:
            Dict[str, List[int]]: Categories with app IDs
            
        Note:
            Default categories can be overridden by providing a config file.
            Config should be JSON format with category names as keys.
        """
        # Default game categories
        default_categories = {
            "successful": [
                730,     # CS:GO
                570,     # Dota 2
                578080,  # PUBG
                1172470, # Apex Legends
                1599340, # Lost Ark
                1091500, # Cyberpunk 2077
                1675200, # Baldur's Gate 3
                1245620  # ELDEN RING
            ],
            "declining": [
                1240440, # Babylon's Fall
                1262900, # New World
                594650,  # Hunt: Showdown
                235960,  # Natural Selection 2
                233860,  # Kenshi
                292030,  # The Witcher 3: Wild Hunt (older title)
                252950   # Rocket League (transitioned to Epic)
            ],
            "experimental": [
                1938090, # Call of Duty: MW3 | Warzone
                1551360, # Forza Horizon 5
                1426210, # Constant Caliber
                1240520, # Redfall
                1675920, # PAYDAY 3
                1332820  # Hogwarts Legacy
            ]
        }
        
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config file: {e}. Using defaults.")
                
        return default_categories
    
    def get_all_game_ids(self) -> List[int]:
        """
        Get all game IDs across all categories.
        
        Returns:
            List[int]: Complete list of game IDs to track
        """
        all_ids = []
        for category_ids in self.game_categories.values():
            all_ids.extend(category_ids)
        return list(set(all_ids))  # Remove duplicates
    
    def collect_current_data(self, 
                            game_ids: Optional[List[int]] = None,
                            include_details: bool = True) -> pd.DataFrame:
        """
        Collect current data from Steam API.
        
        Args:
            game_ids (List[int], optional): Specific games to collect. Default: all
            include_details (bool): Whether to fetch detailed game information
            
        Returns:
            pd.DataFrame: Collected data with columns:
                - app_id: Steam application ID
                - name: Game name
                - player_count: Current player count
                - category: Game category
                - timestamp: Collection timestamp
                - Additional details if include_details=True
                
        The returned DataFrame is also stored in self.collected_data for later use.
        """
        if game_ids is None:
            game_ids = self.get_all_game_ids()
            
        print(f"[{datetime.now()}] Collecting data for {len(game_ids)} games...")
        
        # Collect basic player counts
        player_counts = self.steam_api.get_multiple_player_counts(game_ids)
        timestamp = player_counts.pop('timestamp')
        
        # Build DataFrame
        data_rows = []
        
        for app_id, player_count in player_counts.items():
            row = {
                'app_id': app_id,
                'player_count': player_count,
                'timestamp': timestamp
            }
            
            # Add category information
            for category, ids in self.game_categories.items():
                if app_id in ids:
                    row['category'] = category
                    break
            else:
                row['category'] = 'uncategorized'
            
            # Optionally fetch detailed information
            if include_details:
                details = self.steam_api.get_app_details(app_id)
                if details and 'data' in details:
                    game_data = details['data']
                    row.update({
                        'name': game_data.get('name', ''),
                        'release_date': game_data.get('release_date', {}).get('date', ''),
                        'metacritic_score': game_data.get('metacritic', {}).get('score', ''),
                        'genres': ','.join([g.get('description', '') for g in game_data.get('genres', [])]),
                        'price': game_data.get('price_overview', {}).get('final_formatted', ''),
                        'is_free': game_data.get('is_free', False)
                    })
            
            data_rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data_rows)
        
        # Store in memory
        collection_key = datetime.now().strftime('%Y-%m-%d-%H-%M')
        self.collected_data[collection_key] = df
        
        return df
    
    def save_data(self, 
                  data: Optional[pd.DataFrame] = None,
                  filename: Optional[str] = None,
                  compress: bool = False) -> str:
        """
        Save collected data to disk.
        
        Args:
            data (pd.DataFrame, optional): Data to save. Default: most recent collection
            filename (str, optional): Custom filename. Default: auto-generated
            compress (bool): Whether to compress the file
            
        Returns:
            str: Path to saved file
            
        Note:
            Compressed files are saved as CSV with gzip compression to save space.
        """
        # Get data to save
        if data is None:
            if not self.collected_data:
                raise ValueError("No data to save. Collect data first.")
            latest_key = max(self.collected_data.keys())
            data = self.collected_data[latest_key]
            
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
            extension = '.csv.gz' if compress else '.csv'
            filename = f"steam_data_{timestamp}{extension}"
            
        # Save file
        filepath = self.data_dir / filename
        
        if compress:
            data.to_csv(filepath, index=False, compression='gzip')
        else:
            data.to_csv(filepath, index=False)
            
        print(f"[{datetime.now()}] Data saved to {filepath}")
        return str(filepath)
    
    def load_data(self, filepath: Union[str, Path]) -> pd.DataFrame:
        """
        Load data from file.
        
        Args:
            filepath (Union[str, Path]): Path to data file
            
        Returns:
            pd.DataFrame: Loaded data
            
        Automatically handles compressed files based on extension.
        """
        filepath = Path(filepath)
        
        # Handle relative paths
        if not filepath.is_absolute():
            filepath = self.data_dir / filepath
            
        # Check if file exists
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
            
        # Load data based on compression
        if filepath.suffix == '.gz':
            df = pd.read_csv(filepath, compression='gzip')
        else:
            df = pd.read_csv(filepath)
            
        print(f"[{datetime.now()}] Loaded data from {filepath}")
        return df
    
    def merge_historical_data(self, 
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             categories: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Merge multiple historical data files.
        
        Args:
            start_date (str, optional): Start date filter (YYYY-MM-DD)
            end_date (str, optional): End date filter (YYYY-MM-DD)
            categories (List[str], optional): Filter by game categories
            
        Returns:
            pd.DataFrame: Merged historical data
            
        This method is crucial for time series analysis and model training.
        """
        # Find all data files
        data_files = list(self.data_dir.glob("steam_data_*.csv*"))
        
        if not data_files:
            print(f"No data files found in {self.data_dir}")
            return pd.DataFrame()
            
        print(f"[{datetime.now()}] Found {len(data_files)} data files to merge")
        
        # Load and merge all files
        dfs = []
        for file_path in data_files:
            try:
                df = self.load_data(file_path)
                dfs.append(df)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                
        if not dfs:
            return pd.DataFrame()
            
        # Concatenate all dataframes
        merged_df = pd.concat(dfs, ignore_index=True)
        
        # Convert timestamp to datetime
        merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'])
        
        # Apply filters
        if start_date:
            merged_df = merged_df[merged_df['timestamp'] >= start_date]
        if end_date:
            merged_df = merged_df[merged_df['timestamp'] <= end_date]
        if categories:
            merged_df = merged_df[merged_df['category'].isin(categories)]
            
        # Sort by timestamp
        merged_df = merged_df.sort_values('timestamp')
        
        print(f"[{datetime.now()}] Merged {len(merged_df)} records")
        return merged_df
    
    def run_collection_loop(self, 
                           interval_hours: int = 24,
                           duration_days: int = 30,
                           save_interval: int = 1) -> None:
        """
        Run continuous data collection in a loop.
        
        Args:
            interval_hours (int): Hours between collections
            duration_days (int): Total days to run
            save_interval (int): Hours between saves (default: each collection)
            
        Note:
            This is a simple implementation. For production, use a proper
            scheduler like Airflow or cron jobs.
        """
        end_time = datetime.now() + timedelta(days=duration_days)
        collection_count = 0
        
        print(f"[{datetime.now()}] Starting collection loop...")
        print(f"Collecting every {interval_hours} hours for {duration_days} days")
        print(f"Collection will end at: {end_time}")
        
        while datetime.now() < end_time:
            try:
                # Collect data
                df = self.collect_current_data()
                collection_count += 1
                
                # Save data
                self.save_data(df)
                
                # Print summary
                print(f"\nCollection #{collection_count} Summary:")
                print(f"  Games: {len(df)}")
                print(f"  Total Players: {df['player_count'].sum():,}")
                print(f"  Top Game: {df.nlargest(1, 'player_count').iloc[0]['name']} ({df['player_count'].max():,} players)")
                
                # Calculate sleep time
                next_collection = datetime.now() + timedelta(hours=interval_hours)
                sleep_seconds = (next_collection - datetime.now()).total_seconds()
                
                print(f"  Next collection at: {next_collection}")
                print(f"  Sleeping for {sleep_seconds/3600:.1f} hours...")
                
                # Sleep until next collection
                time.sleep(sleep_seconds)
                
            except KeyboardInterrupt:
                print(f"\n[{datetime.now()}] Collection loop stopped by user")
                break
            except Exception as e:
                print(f"\n[{datetime.now()}] Error in collection loop: {e}")
                print("Continuing in 10 seconds...")
                time.sleep(10)
        
        print(f"\n[{datetime.now()}] Collection loop completed. Total collections: {collection_count}")
    
    def get_collection_summary(self) -> Dict:
        """
        Get summary of collected data.
        
        Returns:
            Dict: Summary statistics including:
                - Number of collections
                - Date range
                - Game counts by category
                - Data file information
        """
        summary = {
            'in_memory_collections': len(self.collected_data),
            'game_categories': {k: len(v) for k, v in self.game_categories.items()},
            'total_games': len(self.get_all_game_ids()),
            'data_files': []
        }
        
        # Get information about saved files
        data_files = list(self.data_dir.glob("steam_data_*.csv*"))
        for file_path in data_files:
            file_info = {
                'filename': file_path.name,
                'size_mb': file_path.stat().st_size / (1024 * 1024),
                'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
            summary['data_files'].append(file_info)
        
        return summary