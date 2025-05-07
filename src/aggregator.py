import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
import warnings

# Ignore specific warnings that might arise from mean of empty slice
warnings.filterwarnings("ignore", category=RuntimeWarning, message="Mean of empty slice")

class DataAggregator:
    """
    Aggregates time-series game data into pre-release features and post-launch outcomes.

    Reads historical data collected by DataCollector (expected in CSV format),
    processes it based on game release dates, and generates a summary DataFrame
    suitable for modeling.
    """
    def __init__(self, data_dir: str = "data"):
        """
        Initializes the DataAggregator.

        Args:
            data_dir (str): The directory where DataCollector saves its CSV files.
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
             print(f"Warning: Data directory '{self.data_dir}' does not exist.")


    def load_merged_data(self, file_pattern: str = "steam_data_*.csv*") -> pd.DataFrame:
        """
        Loads and merges all historical data files matching the pattern.

        Args:
            file_pattern (str): Glob pattern for the data files saved by DataCollector.

        Returns:
            pd.DataFrame: A single DataFrame containing all historical records,
                          sorted by timestamp. Returns an empty DataFrame if no files found.
        """
        print(f"Loading data files from '{self.data_dir}' matching '{file_pattern}'...")
        data_files = sorted(list(self.data_dir.glob(file_pattern))) # Sort to process chronologically if needed later

        if not data_files:
            print("No data files found.")
            return pd.DataFrame()

        dfs = []
        for f in data_files:
            try:
                # Attempt to parse dates, coerce errors to NaT
                df = pd.read_csv(f,
                                 compression='gzip' if f.suffix == '.gz' else None,
                                 parse_dates=['timestamp'], # Parse timestamp first
                                 infer_datetime_format=True)
                # Handle release_date separately as it might not always be a date
                if 'release_date' in df.columns:
                     df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
                dfs.append(df)
            except Exception as e:
                print(f"Error loading file {f}: {e}")
                continue # Skip problematic files

        if not dfs:
             print("No data could be loaded from files.")
             return pd.DataFrame()

        merged_df = pd.concat(dfs, ignore_index=True)
        merged_df = merged_df.sort_values('timestamp').reset_index(drop=True)
        print(f"Loaded and merged {len(merged_df)} records from {len(data_files)} files.")
        return merged_df

    def aggregate_features(self,
                           merged_data: pd.DataFrame,
                           pre_release_days: int = 30,
                           post_launch_days_peak: int = 7,
                           post_launch_days_avg: int = 30) -> pd.DataFrame:
        """
        Aggregates the merged time-series data into features per game.

        Calculates pre-release averages and post-launch peaks/averages based on
        the provided time windows relative to the game's release date.

        Args:
            merged_data (pd.DataFrame): The DataFrame returned by load_merged_data().
            pre_release_days (int): How many days before release to average pre-release signals.
            post_launch_days_peak (int): How many days after launch to find peak engagement metrics.
            post_launch_days_avg (int): How many days after launch to average engagement metrics.

        Returns:
            pd.DataFrame: DataFrame with one row per game, containing aggregated features.
        """
        if merged_data.empty:
            print("Input data is empty. Cannot aggregate.")
            return pd.DataFrame()

        # --- Data Cleaning and Preparation ---
        print("Preparing data for aggregation...")
        # Ensure necessary columns exist, fill missing ones with NA
        # Base columns needed for grouping and time slicing
        ensure_cols = ['app_id', 'name', 'timestamp', 'release_date']
        # Metric columns to be aggregated
        metric_cols = ['player_count', 'twitch_viewer_count', 'google_trends_avg',
                       'reddit_subscribers', 'reddit_active_users', 'reddit_recent_posts',
                       'twitter_recent_count', 'metacritic_score'] # Add others if collected

        for col in ensure_cols + metric_cols:
            if col not in merged_data.columns:
                print(f"  Adding missing column: '{col}'")
                merged_data[col] = pd.NA

        # Convert types robustly
        merged_data['timestamp'] = pd.to_datetime(merged_data['timestamp'], errors='coerce')
        merged_data['release_date'] = pd.to_datetime(merged_data['release_date'], errors='coerce')

        for col in metric_cols:
            merged_data[col] = pd.to_numeric(merged_data[col], errors='coerce')

        # Drop rows where essential time info is missing
        merged_data.dropna(subset=['app_id', 'timestamp'], inplace=True)

        # --- Aggregation Logic ---
        aggregated_results = []
        # Group by app_id, assuming it's the unique game identifier
        grouped = merged_data.groupby('app_id')

        print(f"Aggregating features for {len(grouped)} unique games...")

        for app_id, group in grouped:
            # Use the most recent non-null name and release date for the game
            game_name = group['name'].dropna().iloc[-1] if not group['name'].dropna().empty else f"Unknown Game (ID: {app_id})"
            release_date = group['release_date'].dropna().iloc[-1] if not group['release_date'].dropna().empty else None

            # Skip game if release date is missing
            if pd.isna(release_date):
                print(f"  Skipping game {app_id} ({game_name}): Missing release date.")
                continue

            print(f"  Processing {game_name} (App ID: {app_id}, Release: {release_date.date()})")

            # Define time windows
            pre_release_start = release_date - timedelta(days=pre_release_days)
            post_launch_peak_end = release_date + timedelta(days=post_launch_days_peak)
            post_launch_avg_end = release_date + timedelta(days=post_launch_days_avg)

            # Filter data for pre-release and post-launch periods
            pre_release_data = group[(group['timestamp'] >= pre_release_start) & (group['timestamp'] < release_date)]
            post_launch_data_peak = group[(group['timestamp'] >= release_date) & (group['timestamp'] < post_launch_peak_end)]
            post_launch_data_avg = group[(group['timestamp'] >= release_date) & (group['timestamp'] < post_launch_avg_end)]

            # --- Calculate Pre-Release Features ---
            pre_release_features = {
                'google_trends_avg_pre': pre_release_data['google_trends_avg'].mean(skipna=True),
                'reddit_posts_avg_pre': pre_release_data['reddit_recent_posts'].mean(skipna=True),
                'twitter_count_avg_pre': pre_release_data['twitter_recent_count'].mean(skipna=True),
                # Use last known subscriber/active count before release
                'reddit_subs_pre': pre_release_data['reddit_subscribers'].dropna().iloc[-1] if not pre_release_data['reddit_subscribers'].dropna().empty else None,
                'reddit_active_pre': pre_release_data['reddit_active_users'].dropna().iloc[-1] if not pre_release_data['reddit_active_users'].dropna().empty else None,
            }

            # --- Calculate Post-Launch Outcomes ---
            post_launch_outcomes = {
                f'steam_peak_players_{post_launch_days_peak}d': post_launch_data_peak['player_count'].max(skipna=True),
                f'twitch_peak_viewers_{post_launch_days_peak}d': post_launch_data_peak['twitch_viewer_count'].max(skipna=True),
                f'steam_avg_players_{post_launch_days_avg}d': post_launch_data_avg['player_count'].mean(skipna=True),
                f'twitch_avg_viewers_{post_launch_days_avg}d': post_launch_data_avg['twitch_viewer_count'].mean(skipna=True),
            }

            # --- Static Features (e.g., Metacritic score) ---
            # Use the most recent non-null value available for the game
            static_features = {
                 'metacritic_score': group['metacritic_score'].dropna().iloc[-1] if not group['metacritic_score'].dropna().empty else None,
                 # Add other static features like genre, price if needed
            }


            # Combine results for the game
            result_row = {
                'app_id': app_id,
                'game_name': game_name,
                'release_date': release_date,
                **static_features,
                **pre_release_features,
                **post_launch_outcomes
            }
            # Replace NaN with None for better compatibility (e.g., with JSON) if needed later
            result_row = {k: (None if pd.isna(v) else v) for k, v in result_row.items()}
            aggregated_results.append(result_row)

        print("Aggregation complete.")
        if not aggregated_results:
             print("No games had sufficient data for aggregation.")
             return pd.DataFrame()

        return pd.DataFrame(aggregated_results)
