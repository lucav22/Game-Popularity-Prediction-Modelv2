import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
from typing import List, Dict, Optional, Union, Tuple
from pathlib import Path
import re # Added for cleaning game names

from src.connectors.steam_api_connector import SteamAPIConnector
from src.connectors.twitch_api_connector import TwitchAPIConnector
from src.connectors.external_data_collector import ExternalDataCollector # Added import

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
        
        # Initialize API connectors
        self.steam_api = SteamAPIConnector()
        self.twitch_api = TwitchAPIConnector()
        self.external_collector = ExternalDataCollector() # Added initialization
        
        # Load or initialize game categories
        self.config_path = config_path
        self.game_categories = self._load_game_categories()

        # Define mapping for external platform identifiers
        # Add more specific overrides as needed based on observation
        self.external_platform_mapping = {
            # --- Successful Games ---
            "Counter-Strike 2": {
                "reddit_subreddit": "GlobalOffensive", # Still the main sub
                "twitter_query": '"Counter-Strike 2" OR #CS2',
                "youtube_query": '"Counter-Strike 2" gameplay OR CS2',
                "twitch_name": "Counter-Strike" # Added Twitch name override
            },
            "Dota 2": {
                "reddit_subreddit": "DotA2",
                "twitter_query": '"Dota 2" OR #dota2',
            },
             "PUBG: BATTLEGROUNDS": {
                "reddit_subreddit": "PUBATTLEGROUNDS",
                "twitter_query": '"PUBG" OR #PUBG',
                "google_trends_keyword": "PUBG", # Simpler keyword for trends
                "youtube_query": "PUBG gameplay"
            },
            "Apex Legends™": { # Note the ™ symbol from Steam name
                "reddit_subreddit": "apexlegends",
                "twitter_query": '"Apex Legends" OR #ApexLegends',
                "google_trends_keyword": "Apex Legends", # Remove ™
                "twitch_name": "Apex Legends", # Remove ™
                "youtube_query": '"Apex Legends" gameplay'
            },
             "Lost Ark": {
                "reddit_subreddit": "lostarkgame",
                "twitter_query": '"Lost Ark" OR #LostArkGame',
            },
            "Cyberpunk 2077": {
                "reddit_subreddit": "cyberpunkgame",
                "twitter_query": '"Cyberpunk 2077" OR #Cyberpunk2077',
            },
            "Baldur's Gate 3": {
                "reddit_subreddit": "BaldursGate3",
                "twitter_query": '"Baldurs Gate 3" OR #BaldursGate3 OR #BG3',
                "youtube_query": '"Baldurs Gate 3" gameplay OR BG3'
            },
            "ELDEN RING": {
                "reddit_subreddit": "Eldenring", # Capitalization might matter less here
                "twitter_query": '"ELDEN RING" OR #ELDENRING',
            },
            "Grand Theft Auto V": { # Renamed key from "Grand Theft Auto V Legacy"
                "reddit_subreddit": "GTAV",
                "twitter_query": '"Grand Theft Auto V" OR #GTAV OR #GTAOnline',
                "google_trends_keyword": "Grand Theft Auto V",
                "twitch_name": "Grand Theft Auto V",
                "youtube_query": '"Grand Theft Auto V" OR GTAV gameplay'
            },
            "Valheim": {
                "reddit_subreddit": "valheim",
                "twitter_query": '"Valheim" OR #Valheim',
            },
            # --- Declining Games ---
             "Tom Clancy's Rainbow Six® Siege": {
                "reddit_subreddit": "Rainbow6",
                "twitter_query": '"Rainbow Six Siege" OR #RainbowSixSiege OR #R6S',
                "google_trends_keyword": "Rainbow Six Siege",
                "twitch_name": "Tom Clancy's Rainbow Six Siege",
                "youtube_query": '"Rainbow Six Siege" gameplay OR R6S'
            },
            "Team Fortress 2": {
                "reddit_subreddit": "tf2",
                "twitter_query": '"Team Fortress 2" OR #TF2',
            },
            "Kenshi": {
                "reddit_subreddit": "Kenshi",
                "twitter_query": '"Kenshi game" OR #Kenshi', # Add "game" to disambiguate
            },
            "The Witcher 3: Wild Hunt": {
                "reddit_subreddit": "witcher", # Main Witcher sub
                "twitter_query": '"Witcher 3" OR #Witcher3',
                "google_trends_keyword": "Witcher 3",
            },
            "Rocket League": { # Renamed key from "Rocket League®"
                "reddit_subreddit": "RocketLeague",
                "twitter_query": '"Rocket League" OR #RocketLeague',
                "google_trends_keyword": "Rocket League",
                "twitch_name": "Rocket League",
            },
            # --- Experimental Games ---
            "Call of Duty®": { # This is the HQ, might need specific MW3/Warzone query
                 "reddit_subreddit": "ModernWarfareIII", # Or CODWarzone? Check activity
                 "twitter_query": '#MW3 OR #Warzone OR "Call of Duty"',
                 "google_trends_keyword": "Call of Duty",
                 "twitch_name": "Call of Duty", # Broad category on Twitch
                 "youtube_query": 'Modern Warfare 3 gameplay OR Warzone gameplay'
            },
             "Forza Horizon 5": {
                "reddit_subreddit": "ForzaHorizon",
                "twitter_query": '"Forza Horizon 5" OR #ForzaHorizon5',
            },
            "Sea of Thieves": { # Renamed key from "Sea of Thieves: 2025 Edition"
                "twitch_name": "Sea of Thieves", # Already added
                "reddit_subreddit": "Seaofthieves",
                "twitter_query": '"Sea of Thieves" OR #SeaOfThieves',
                "google_trends_keyword": "Sea of Thieves",
                "youtube_query": '"Sea of Thieves" gameplay'
            },
            # Palworld mapping depends on which game ID 1962660 actually resolved to.
            # Assuming it resolved to "Call of Duty®: Modern Warfare® II" based on notebook output
            "Call of Duty: Modern Warfare II": { # Renamed key from "Call of Duty®: Modern Warfare® II"
                "reddit_subreddit": "ModernWarfareII",
                "twitter_query": '"Modern Warfare 2" OR #MWII OR #MW2',
                "google_trends_keyword": "Modern Warfare 2",
                "twitch_name": "Call of Duty: Modern Warfare II",
                "youtube_query": '"Modern Warfare 2" gameplay OR MW2'
            },
            "NARAKA: BLADEPOINT": {
                "reddit_subreddit": "NarakaBladePoint",
                "twitter_query": '"NARAKA BLADEPOINT" OR #NARAKABLADEPOINT',
            },
        }

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
                730,     # Counter-Strike 2 (was CS:GO)
                570,     # Dota 2
                578080,  # PUBG: BATTLEGROUNDS
                1172470, # Apex Legends
                1599340, # Lost Ark
                1091500, # Cyberpunk 2077
                1086940, # Baldur's Gate 3 (Correct ID)
                1245620, # ELDEN RING
                271590,  # Grand Theft Auto V
                892970,  # Valheim
            ],
            "declining": [
                359550,  # Tom Clancy's Rainbow Six Siege
                440,     # Team Fortress 2
                233860,  # Kenshi
                292030,  # The Witcher 3: Wild Hunt
                252950   # Rocket League
            ],
            "experimental": [
                1938090, # Call of Duty HQ (MW3 | Warzone)
                1551360, # Forza Horizon 5
                1172620, # Sea of Thieves
                1962660, # Palworld
                1203220  # NARAKA: BLADEPOINT
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
                            include_details: bool = True,
                            include_twitch: bool = True,
                            include_external: bool = True,
                            external_signal_timeout_per_game: int = 30) -> pd.DataFrame: # Changed default timeout param
        """
        Collect current data from Steam, optionally Twitch, and optionally external sources.

        Args:
            game_ids (List[int], optional): Specific games to collect. Default: all
            include_details (bool): Whether to fetch detailed game information from Steam
            include_twitch (bool): Whether to fetch current viewership from Twitch
            include_external (bool): Whether to fetch external signals (Google Trends, Reddit, Twitter)
            external_signal_timeout_per_game (int): Max seconds to spend on external signals per game.

        Returns:
            pd.DataFrame: Collected data with columns including:
                - app_id, name, player_count, category, timestamp
                - twitch_viewer_count (if include_twitch=True)
                - Steam details (if include_details=True)
                - google_trends_avg, reddit_subscribers, reddit_active_users,
                  reddit_recent_posts, twitter_recent_count (if include_external=True)

        The returned DataFrame is also stored in self.collected_data for later use.
        """
        if game_ids is None:
            game_ids = self.get_all_game_ids()

        print(f"[{datetime.now()}] Collecting data for {len(game_ids)} games...")

        # Collect basic player counts from Steam
        player_counts = self.steam_api.get_multiple_player_counts(game_ids)
        timestamp = player_counts.pop('timestamp')

        # Build initial DataFrame rows with Steam/Twitch data
        data_rows = []
        game_names_for_external = [] # List to store names for external collection

        for app_id, player_count in player_counts.items():
            row = {
                'app_id': app_id,
                'player_count': player_count,
                'timestamp': timestamp,
                'name': '', # Initialize name
                'twitch_viewer_count': None, # Initialize twitch count
                # Initialize external signal columns
                'google_trends_avg': None,
                'reddit_subscribers': None,
                'reddit_active_users': None,
                'reddit_recent_posts': None, # Name will depend on time_filter used
                'twitter_recent_count': None,
                # Initialize YouTube columns
                'youtube_total_views': None,
                'youtube_avg_views': None,
                'youtube_avg_likes': None,
            }

            # Add category information
            for category, ids in self.game_categories.items():
                if app_id in ids:
                    row['category'] = category
                    break
            else:
                row['category'] = 'uncategorized'

            # Fetch detailed information from Steam (includes game name needed for Twitch/External)
            game_name = None
            if include_details:
                details = self.steam_api.get_app_details(app_id)
                if details and 'data' in details:
                    game_data = details['data']
                    game_name = game_data.get('name') # Get game name
                    row.update({
                        'name': game_name,
                        'release_date': game_data.get('release_date', {}).get('date', ''),
                        'metacritic_score': game_data.get('metacritic', {}).get('score', ''),
                        'genres': ','.join([g.get('description', '') for g in game_data.get('genres', [])]),
                        'price': game_data.get('price_overview', {}).get('final_formatted', ''),
                        'is_free': game_data.get('is_free', False)
                    })
                    if game_name:
                         game_names_for_external.append(game_name) # Add valid name for external collection

            # Fetch Twitch viewership if requested and game name is available
            if include_twitch and game_name:
                # Clean the game name for Twitch API
                # Remove common trademark symbols and specific edition texts
                # Order of replacements can matter if one is a substring of another
                cleaned_game_name = game_name.replace('™', '')\
                                           .replace('®', '')\
                                           .replace('(R)', '')\
                                           .replace('(TM)', '')
                # Remove year-based editions like ": 2025 Edition" or "(2024)"
                cleaned_game_name = re.sub(r'[:(]\s*\d{4}\s*(Edition|Update)?\s*[)]?', '', cleaned_game_name, flags=re.IGNORECASE)
                # Remove other generic edition/version markers if they are at the end of the string
                # Ensure to handle cases with or without "Edition", "Version", "Pack" at the very end.
                cleaned_game_name = re.sub(r'\s*:\s*(Definitive|Ultimate|GOTY|Standard|Deluxe|Gold|Collector\'s|Anniversary|Remastered|Legacy|Founder\'s)(\s+(Edition|Version|Pack))?$', '', cleaned_game_name, flags=re.IGNORECASE)
                # Remove any leading/trailing whitespace that might have been introduced
                cleaned_game_name = cleaned_game_name.strip()

                # Use an override from external_platform_mapping if available for Twitch name
                twitch_name_to_query = self.external_platform_mapping.get(game_name, {}).get('twitch_name', cleaned_game_name)

                print(f"  Fetching Twitch data for: {game_name} (Querying as: '{twitch_name_to_query}')")
                twitch_game_id = self.twitch_api.get_game_id_by_name(twitch_name_to_query)
                if twitch_game_id:
                    viewers = self.twitch_api.get_game_viewership(twitch_game_id)
                    row['twitch_viewer_count'] = viewers
                    print(f"    > Twitch ID: {twitch_game_id}, Viewers: {viewers}")
                else:
                    print(f"    > Could not find Twitch game ID for {twitch_name_to_query}")
            elif include_twitch and not game_name:
                  print(f"  Skipping Twitch for app_id {app_id} (no name found/details not included)")


            data_rows.append(row)

        # Collect external signals if requested
        external_signals_data = {}
        if include_external and game_names_for_external:
            # Use default timeframes from collect_external_signals method signature for now
            # These could be made parameters of collect_current_data if needed
            external_signals_data = self.external_collector.collect_external_signals( # Changed from self.collect_external_signals
                game_names=list(set(game_names_for_external)), # Use unique names
                platform_mapping=self.external_platform_mapping, # Pass the mapping
                timeout_per_game_seconds=external_signal_timeout_per_game # Pass the timeout
                # Pass other parameters like timeframes if needed
            )

        # Merge external signals back into data_rows
        if external_signals_data:
            print(f"[{datetime.now()}] Merging external signals into main dataset...")
            for row in data_rows:
                game_name = row.get('name')
                if game_name and game_name in external_signals_data:
                    signals = external_signals_data[game_name]
                    row['google_trends_avg'] = signals.get('google_trends_avg')

                    reddit_data = signals.get('reddit_data')
                    if reddit_data:
                        row['reddit_subscribers'] = reddit_data.get('subscribers')
                        row['reddit_active_users'] = reddit_data.get('active_users')
                        # Find the post count key (depends on the time_filter used in collect_external_signals)
                        post_count_key = next((k for k in reddit_data if k.startswith('recent_post_count_')), None)
                        if post_count_key:
                            row['reddit_recent_posts'] = reddit_data.get(post_count_key)

                    twitter_data = signals.get('twitter_data')
                    if twitter_data:
                        row['twitter_recent_count'] = twitter_data.get('recent_tweet_count')

                    youtube_data = signals.get('youtube_data')
                    if youtube_data:
                        # Find the keys dynamically as they include the count N
                        total_views_key = next((k for k in youtube_data if k.startswith('total_views_top_')), None)
                        avg_views_key = next((k for k in youtube_data if k.startswith('avg_views_top_')), None)
                        avg_likes_key = next((k for k in youtube_data if k.startswith('avg_likes_top_')), None)

                        if total_views_key:
                            row['youtube_total_views'] = youtube_data.get(total_views_key)
                        if avg_views_key:
                            row['youtube_avg_views'] = youtube_data.get(avg_views_key)
                        if avg_likes_key:
                            row['youtube_avg_likes'] = youtube_data.get(avg_likes_key)

            print(f"[{datetime.now()}] Finished merging external signals.")


        # Create DataFrame
        df = pd.DataFrame(data_rows)

        # Reorder columns for better readability (optional)
        cols_order = [
            'app_id', 'name', 'category', 'timestamp', 'player_count', 'twitch_viewer_count',
            'google_trends_avg', 'reddit_subscribers', 'reddit_active_users', 'reddit_recent_posts', 'twitter_recent_count',
            'youtube_total_views', 'youtube_avg_views', 'youtube_avg_likes', # Added YouTube cols
            'release_date', 'metacritic_score', 'genres', 'price', 'is_free'
        ]
        # Filter out columns not present in the DataFrame before reordering
        cols_order_present = [col for col in cols_order if col in df.columns]
        df = df[cols_order_present]


        # Store in memory
        collection_key = datetime.now().strftime('%Y-%m-%d-%H-%M')
        self.collected_data[collection_key] = df

        print(f"[{datetime.now()}] Data collection complete. DataFrame shape: {df.shape}")
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