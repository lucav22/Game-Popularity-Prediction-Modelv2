import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Tuple
import json
from pathlib import Path

# Set plotting style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_context("talk")

def configure_plotting(style: str = 'seaborn-v0_8-whitegrid', 
                      context: str = 'talk',
                      figsize: Tuple[int, int] = (14, 8)) -> None:
    """
    Configure matplotlib and seaborn plotting settings.
    
    Args:
        style (str): Matplotlib style
        context (str): Seaborn context
        figsize (Tuple[int, int]): Default figure size
    """
    plt.style.use(style)
    sns.set_context(context)
    plt.rcParams['figure.figsize'] = figsize

def format_large_numbers(value: float, format_type: str = 'auto') -> str:
    """
    Format large numbers for display.
    
    Args:
        value (float): Number to format
        format_type (str): 'auto', 'thousands', 'millions', or 'billions'
        
    Returns:
        str: Formatted number with units
    """
    if format_type == 'auto':
        if value >= 1e9:
            return f"{value/1e9:.1f}B"
        elif value >= 1e6:
            return f"{value/1e6:.1f}M"
        elif value >= 1e3:
            return f"{value/1e3:.1f}K"
        else:
            return f"{value:.0f}"
    elif format_type == 'thousands':
        return f"{value/1e3:.1f}K"
    elif format_type == 'millions':
        return f"{value/1e6:.1f}M"
    elif format_type == 'billions':
        return f"{value/1e9:.1f}B"
    else:
        return f"{value:.0f}"

def calculate_retention_metrics(df: pd.DataFrame,
                              time_window: str = '7D',
                              player_col: str = 'player_count') -> pd.DataFrame:
    """
    Calculate retention metrics for games over time.
    
    Args:
        df (pd.DataFrame): Time series data with player counts
        time_window (str): Time window for retention calculation (e.g., '7D', '30D')
        player_col (str): Column name for player count
        
    Returns:
        pd.DataFrame: Retention metrics by game
    """
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must contain 'timestamp' column")
    
    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Group by game and calculate retention
    retention_data = []
    
    for app_id in df['app_id'].unique():
        game_data = df[df['app_id'] == app_id].sort_values('timestamp')
        
        if len(game_data) <= 1:
            continue
            
        # Calculate retention metrics
        first_value = game_data[player_col].iloc[0]
        latest_value = game_data[player_col].iloc[-1]
        max_value = game_data[player_col].max()
        
        # Calculate percentage changes
        if first_value > 0:
            retention_pct = (latest_value / first_value) * 100
            peak_retention = (latest_value / max_value) * 100
        else:
            retention_pct = 0
            peak_retention = 0
            
        retention_data.append({
            'app_id': app_id,
            'name': game_data['name'].iloc[0] if 'name' in game_data.columns else '',
            'first_player_count': first_value,
            'latest_player_count': latest_value,
            'peak_player_count': max_value,
            'retention_percentage': retention_pct,
            'peak_retention_percentage': peak_retention,
            'data_points': len(game_data)
        })
    
    return pd.DataFrame(retention_data)

def plot_category_comparison(df: pd.DataFrame,
                           player_col: str = 'player_count',
                           category_col: str = 'category',
                           plot_type: str = 'box') -> plt.Figure:
    """
    Create comparison plots across game categories.
    
    Args:
        df (pd.DataFrame): Data to plot
        player_col (str): Column name for player count
        category_col (str): Column name for categories
        plot_type (str): 'box', 'violin', or 'bar'
        
    Returns:
        plt.Figure: The created figure
    """
    if category_col not in df.columns or player_col not in df.columns:
        raise ValueError(f"DataFrame missing required columns: {category_col}, {player_col}")
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    if plot_type == 'box':
        sns.boxplot(x=category_col, y=player_col, data=df, ax=ax)
    elif plot_type == 'violin':
        sns.violinplot(x=category_col, y=player_col, data=df, ax=ax)
    elif plot_type == 'bar':
        # Calculate mean player count by category
        category_means = df.groupby(category_col)[player_col].mean().reset_index()
        sns.barplot(x=category_col, y=player_col, data=category_means, ax=ax)
    else:
        raise ValueError(f"Unsupported plot type: {plot_type}")
    
    ax.set_title(f'Player Count Distribution by Category ({plot_type.capitalize()} Plot)')
    ax.set_xlabel('Game Category')
    ax.set_ylabel('Player Count')
    
    # Format y-axis for large numbers
    ax.set_yticks(ax.get_yticks())
    ax.set_yticklabels([format_large_numbers(y) for y in ax.get_yticks()])
    
    plt.tight_layout()
    return fig

def analyze_temporal_patterns(df: pd.DataFrame,
                            freq: str = 'D',
                            player_col: str = 'player_count') -> pd.DataFrame:
    """
    Analyze temporal patterns in player data.
    
    Args:
        df (pd.DataFrame): Time series data
        freq (str): Frequency for resampling ('D', 'W', 'M')
        player_col (str): Column name for player count
        
    Returns:
        pd.DataFrame: Analyzed patterns including trend and seasonality
    """
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must contain 'timestamp' column")
    
    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Set timestamp as index
    df_ts = df.set_index('timestamp')
    
    # Analyze patterns by app_id
    pattern_results = []
    
    for app_id in df['app_id'].unique():
        game_data = df_ts[df_ts['app_id'] == app_id]
        
        if len(game_data) < 7:  # Need at least a week of data
            continue
            
        # Resample to specified frequency
        game_ts = game_data[player_col].resample(freq).mean()
        
        # Calculate basic trend
        time_range = (game_ts.index.max() - game_ts.index.min()).days
        if time_range > 0:
            trend_slope = (game_ts.iloc[-1] - game_ts.iloc[0]) / time_range
        else:
            trend_slope = 0
            
        # Detect weekly seasonality (if enough data)
        if len(game_ts) >= 14 and freq == 'D':
            weekly_pattern = game_ts.groupby(game_ts.index.dayofweek).mean()
            seasonal_strength = weekly_pattern.std() / weekly_pattern.mean()
        else:
            seasonal_strength = 0
            
        pattern_results.append({
            'app_id': app_id,
            'name': game_data['name'].iloc[0] if 'name' in game_data.columns else '',
            'trend_slope': trend_slope,
            'seasonal_strength': seasonal_strength,
            'average_player_count': game_ts.mean(),
            'std_dev': game_ts.std(),
            'coefficient_of_variation': game_ts.std() / game_ts.mean() if game_ts.mean() > 0 else 0
        })
    
    return pd.DataFrame(pattern_results)

def create_trend_visualization(df: pd.DataFrame,
                             app_ids: Optional[List[int]] = None,
                             n_games: int = 5,
                             player_col: str = 'player_count') -> plt.Figure:
    """
    Create a trend visualization for multiple games.
    
    Args:
        df (pd.DataFrame): Time series data
        app_ids (List[int], optional): Specific app IDs to plot
        n_games (int): Number of top games to plot if app_ids not provided
        player_col (str): Column name for player count
        
    Returns:
        plt.Figure: The created figure
    """
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must contain 'timestamp' column")
    
    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Select games to plot
    if app_ids is None:
        # Get top N games by average player count
        top_games = df.groupby('app_id')[player_col].mean().nlargest(n_games).index.tolist()
        app_ids = top_games
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for app_id in app_ids:
        game_data = df[df['app_id'] == app_id].sort_values('timestamp')
        
        if len(game_data) <= 1:
            continue
            
        # Get game name
        name = game_data['name'].iloc[0] if 'name' in game_data.columns else f"Game {app_id}"
        
        # Plot the trend
        ax.plot(game_data['timestamp'], game_data[player_col], 
               marker='o', linewidth=2, label=name, markersize=6)
    
    ax.set_xlabel('Date')
    ax.set_ylabel('Player Count')
    ax.set_title('Player Count Trends Over Time')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # Format y-axis for large numbers
    ax.set_yticks(ax.get_yticks())
    ax.set_yticklabels([format_large_numbers(y) for y in ax.get_yticks()])
    
    # Rotate x-axis labels
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return fig

def detect_anomalies(df: pd.DataFrame,
                    player_col: str = 'player_count',
                    threshold: float = 3.0) -> pd.DataFrame:
    """
    Detect anomalies in player count data.
    
    Args:
        df (pd.DataFrame): Time series data
        player_col (str): Column name for player count
        threshold (float): Z-score threshold for anomaly detection
        
    Returns:
        pd.DataFrame: Detected anomalies with details
    """
    anomalies = []
    
    for app_id in df['app_id'].unique():
        game_data = df[df['app_id'] == app_id].copy()
        
        if len(game_data) < 3:  # Need at least 3 data points
            continue
            
        # Calculate z-scores
        game_data['z_score'] = (game_data[player_col] - game_data[player_col].mean()) / game_data[player_col].std()
        
        # Identify anomalies
        game_anomalies = game_data[abs(game_data['z_score']) > threshold]
        
        for _, anomaly in game_anomalies.iterrows():
            anomalies.append({
                'app_id': app_id,
                'name': anomaly.get('name', ''),
                'timestamp': anomaly['timestamp'],
                'player_count': anomaly[player_col],
                'z_score': anomaly['z_score'],
                'type': 'spike' if anomaly['z_score'] > 0 else 'drop'
            })
    
    return pd.DataFrame(anomalies)

def generate_collection_report(collector) -> Dict:
    """
    Generate a comprehensive report of data collection status.
    
    Args:
        collector: Instance of DataCollector
        
    Returns:
        Dict: Comprehensive collection report
    """
    summary = collector.get_collection_summary()
    
    # Get the latest collected data for analysis
    latest_data = None
    if collector.collected_data:
        latest_key = max(collector.collected_data.keys())
        latest_data = collector.collected_data[latest_key]
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'collection_summary': summary,
        'api_statistics': collector.steam_api.get_api_statistics(),
        'health_metrics': {}
    }
    
    if latest_data is not None:
        # Calculate health metrics
        report['health_metrics'] = {
            'total_players': latest_data['player_count'].sum(),
            'average_players_per_game': latest_data['player_count'].mean(),
            'most_popular_game': latest_data.nlargest(1, 'player_count').iloc[0]['name'] if 'name' in latest_data.columns else 'Unknown',
            'category_distribution': latest_data['category'].value_counts().to_dict()
        }
    
    return report

def export_config(config: Dict, filepath: Union[str, Path]) -> None:
    """
    Export configuration to JSON file.
    
    Args:
        config (Dict): Configuration dictionary
        filepath (Union[str, Path]): Path to save configuration
    """
    filepath = Path(filepath)
    
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=4)
    
    print(f"Configuration exported to {filepath}")

def load_config(filepath: Union[str, Path]) -> Dict:
    """
    Load configuration from JSON file.
    
    Args:
        filepath (Union[str, Path]): Path to configuration file
        
    Returns:
        Dict: Loaded configuration
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"Configuration file not found: {filepath}")
    
    with open(filepath, 'r') as f:
        config = json.load(f)
    
    print(f"Configuration loaded from {filepath}")
    return config