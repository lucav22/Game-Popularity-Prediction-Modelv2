import time
import os
import re # Import re for cleaning names
from typing import Dict, List, Optional
import pandas as pd # Added for pytrends
import datetime
from dotenv import load_dotenv # Added for .env support
import requests # Added for session management

# Import specific libraries
try:
    from pytrends.request import TrendReq
except ImportError:
    print("Warning: pytrends library not found. Google Trends functionality will be unavailable.")
    TrendReq = None

# Placeholder for other imports
try:
    import praw
    import prawcore # Import prawcore for specific exceptions
except ImportError:
    print("Warning: praw library not found. Reddit functionality will be unavailable.")
    praw = None
    prawcore = None

# Import tweepy
try:
    import tweepy
except ImportError:
    print("Warning: tweepy library not found. Twitter functionality will be unavailable.")
    tweepy = None

# Google API Client
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Warning: google-api-python-client not found. YouTube functionality will be unavailable.")
    build = None
    HttpError = None

class ExternalDataCollector:
    """
    A placeholder class to handle connections to external data sources like Reddit, Twitter, YouTube, Twitch.
    Requires implementation using platform-specific APIs and libraries.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the external data collector.
        Args:
            config (Dict, optional): Dictionary containing API keys/credentials for various platforms.
                                     Example: {'reddit': {'client_id': '...', 'client_secret': '...'},
                                               'twitter': {'bearer_token': '...'}}
        """
        self.config = config or self._load_config_from_env()
        
        # Initialize requests session for pytrends
        self.pytrends_session = requests.Session()
        self.pytrends_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        self.pytrends_session.verify = False # To address potential SSL issues with custom UAs

        # Twitter API rate limiting state
        self.twitter_last_api_call_time = 0
        # Free tier: 100 requests per 15-minute window for recent tweet counts.
        # 15 min * 60 sec/min = 900 seconds.
        # 900 seconds / 100 requests = 9 seconds per request.
        # Add a buffer, so let's aim for slightly more than 9s, e.g., 10s.
        self.twitter_min_interval = 15  # Seconds - Increased from 10 to 15
        self.twitter_rate_limit_cooldown = 15 * 60 + 15 # 15 minutes + 15s buffer in seconds
        self.twitter_is_in_cooldown = False
        self.twitter_cooldown_until = 0 # Timestamp until which cooldown is active

        # Initialize API clients
        self.reddit_client = self._init_reddit()
        self.twitter_client = self._init_twitter()
        self.pytrends_client = self._init_pytrends() # Initialize pytrends client

        # Add rate limiting / error handling structures if needed centrally, or handle in each method
        print("ExternalDataCollector initialized")

    def _load_config_from_env(self) -> Dict:
        # Load .env file variables into environment
        print("[ExternalDataCollector] Attempting to load .env file...")
        found_dotenv = load_dotenv()
        print(f"[ExternalDataCollector] .env file found and loaded: {found_dotenv}")

        # Debug: Print loaded Reddit environment variables
        reddit_client_id_env = os.environ.get('REDDIT_CLIENT_ID')
        reddit_client_secret_env = os.environ.get('REDDIT_CLIENT_SECRET')
        reddit_user_agent_env = os.environ.get('REDDIT_USER_AGENT')

        twitter_bearer_token_env = os.environ.get('TWITTER_BEARER_TOKEN')
        try:
            twitter_request_timeout_env = float(os.environ.get('TWITTER_REQUEST_TIMEOUT', '20.0'))
            if twitter_request_timeout_env <= 0:
                print(f"Warning: Invalid TWITTER_REQUEST_TIMEOUT value ({twitter_request_timeout_env}). Defaulting to 20.0 seconds.")
                twitter_request_timeout_env = 20.0
        except (ValueError, TypeError):
            print(f"Warning: Could not parse TWITTER_REQUEST_TIMEOUT. Defaulting to 20.0 seconds.")
            twitter_request_timeout_env = 20.0


        # Example: Load necessary API keys from environment variables
        config = {
            'reddit': {
                'client_id': reddit_client_id_env,
                'client_secret': reddit_client_secret_env,
                'user_agent': reddit_user_agent_env or 'game_popularity_bot/0.1' # Fallback if None
            },
            'twitter': {
                'bearer_token': twitter_bearer_token_env,
                'request_timeout': twitter_request_timeout_env # Added Twitter request timeout
            },
            # Add other platforms (YouTube, Twitch, Steam) if needed here
            'twitch': { # Added Twitch example
                'client_id': os.environ.get('TWITCH_CLIENT_ID'),
                'client_secret': os.environ.get('TWITCH_CLIENT_SECRET')
            },
            'steam': { # Added Steam example
                'api_key': os.environ.get('STEAM_API_KEY')
            },
            'youtube': { # Added YouTube example
                'api_key': os.environ.get('YOUTUBE_API_KEY')
            }
        }
        return config

    # --- Initialization Methods ---
    def _init_pytrends(self):
        if TrendReq is None:
            print("Error: pytrends library not installed. Google Trends functionality will be unavailable.")
            return None
        
        # Attempt to log version, but don't fail if __version__ is missing
        try:
            import pytrends # Make sure pytrends is importable at the top level
            # Check for __version__ attribute safely
            version = getattr(pytrends, '__version__', 'unknown (attribute missing)')
            print(f"[ExternalDataCollector._init_pytrends] Detected pytrends library version: {version}")
        except ImportError:
            print("[ExternalDataCollector._init_pytrends] Could not import top-level \'pytrends\' package. Is it installed correctly?")
            # We might still proceed if TrendReq was imported successfully earlier
        except Exception as e: 
            print(f"[ExternalDataCollector._init_pytrends] Error determining pytrends library version: {e}")

        # Attempt initialization with 'requests_session' first
        try:
            client = TrendReq(
                hl='en-US', 
                tz=360, 
                timeout=(15, 30),
                requests_session=self.pytrends_session # self.pytrends_session has verify=False set in __init__
            )
            print("Pytrends client initialized successfully with a shared session (using \'requests_session\').")
            return client
        except TypeError as e:
            if "unexpected keyword argument 'requests_session'" in str(e) or \
               "__init__() got an unexpected keyword argument 'requests_session'" in str(e):
                print("Warning: Installed pytrends version does not support \'requests_session\'. Falling back to basic initialization with requests_args.")
                print("         Consider checking your pytrends installation (target version 4.7.0+ for full support).")
                # Fallback: Initialize without requests_session, but with requests_args for SSL verification
                try:
                    client = TrendReq(
                        hl='en-US', 
                        tz=360, 
                        timeout=(15, 30),
                        requests_args={'verify': False} # Ensure this is applied in fallback
                    )
                    print("Pytrends client initialized successfully (fallback, with requests_args for SSL verification).")
                    return client
                except Exception as fallback_e:
                    print(f"Error initializing Pytrends client (fallback attempt failed): {fallback_e}")
                    return None
            else:
                print(f"Error initializing Pytrends client (unexpected TypeError): {e}")
                return None
        except Exception as e:
            print(f"Error initializing Pytrends client: {e}")
            return None

    def _init_reddit(self):
        if praw is None:
            print("Error: praw library not installed, cannot initialize Reddit client.")
            return None
        
        reddit_config = self.config.get('reddit', {})
        client_id = reddit_config.get('client_id')
        client_secret = reddit_config.get('client_secret')
        # Use the user_agent from config, which has a fallback in _load_config_from_env
        user_agent = reddit_config.get('user_agent') 

        if client_id and client_secret and user_agent:
            try:
                # For script-based authentication (app-only, read-only for most operations),
                # PRAW handles token acquisition and refresh automatically using client_id and client_secret.
                # The client will be in a read-only state by default with this authentication method.
                reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                    timeout=15, # Set a request timeout (seconds)
                    check_for_async=False # Added to match test_reddit_auth.py
                )
                if reddit:
                    # Accessing reddit.read_only confirms PRAW is initialized and in read-only mode.
                    # This doesn't fetch a token explicitly but prepares PRAW for API calls.
                    _ = reddit.read_only 
                    print("Reddit client initialized successfully (read-only mode).")
                    return reddit
                else:
                    print("Error: Failed to initialize Reddit client object.")
                    return None
            except prawcore.exceptions.OAuthException as e:
                print(f"Error initializing Reddit client (OAuthException): {e}. Check credentials.")
                return None
            except Exception as e:
                print(f"Error initializing Reddit client: {e}")
                return None
        else:
            print("Warning: Reddit client_id, client_secret, or user_agent missing. Cannot initialize Reddit client.")
            return None

    def _init_twitter(self):
        if tweepy is None:
            print("Error: tweepy library not installed, cannot initialize Twitter client.")
            return None
        
        twitter_config = self.config.get('twitter', {})
        bearer_token = twitter_config.get('bearer_token')
        # Get request_timeout from config, default to 20.0 seconds if not found
        request_timeout = twitter_config.get('request_timeout', 20.0) 

        if bearer_token:
            try:
                # Initialize Tweepy client for API v2 with the specified timeout
                client = tweepy.Client(bearer_token, timeout=request_timeout)
                print(f"Twitter client initialized successfully (Bearer Token loaded, request timeout: {request_timeout}s).")
                return client
            except Exception as e:
                print(f"Error initializing Twitter client: {e}")
                return None
        else:
            print("Warning: Twitter bearer_token missing. Cannot initialize Twitter client.")
            return None

    def collect_external_signals(self,
                                 game_names: List[str],
                                 platform_mapping: Dict[str, Dict[str, str]] = {},
                                 google_trends_timeframe: str = 'today 1-m',
                                 reddit_time_filter: str = 'week',
                                 twitter_time_window_minutes: int = 60 * 24, # Last 24 hours
                                 youtube_max_results: int = 5,
                                 timeout_per_game_seconds: int = 60  # Changed default timeout param
                                 ) -> Dict[str, Dict]:
        """
        Collects external signals (Google Trends, Reddit, Twitter, YouTube) for a list of game names,
        using platform-specific overrides where provided.

        Args:
            game_names (List[str]): A list of game names (usually from Steam) to collect signals for.
            platform_mapping (Dict[str, Dict[str, str]]): Overrides for platform identifiers.
            google_trends_timeframe (str): Timeframe for Google Trends data.
            reddit_time_filter (str): Time filter for Reddit post counts.
            twitter_time_window_minutes (int): Time window in minutes for Twitter recent counts.
            youtube_max_results (int): Max YouTube search results to process.
            timeout_per_game_seconds (int): Maximum time in seconds to spend collecting data for a single game.
                                            Defaults to 30 seconds.

        Returns:
            Dict[str, Dict]: A dictionary where keys are game names and values are dictionaries
                             containing the collected signals.
        """
        print(f"[{datetime.datetime.now()}] Collecting external signals for {len(game_names)} games...")
        external_data = {}

        for name in game_names:
            game_start_time = time.time() # Start timer for this game
            print(f"  Processing external signals for: {name} (Timeout: {timeout_per_game_seconds}s)")
            game_signals = {}
            timed_out_for_game = False
            # Get all overrides for this specific game, default to empty dict if none
            overrides = platform_mapping.get(name, {})

            # --- Helper function to check timeout ---
            def check_timeout(signal_name: str) -> bool:
                nonlocal timed_out_for_game # Allow modification of the outer scope variable
                if timed_out_for_game: # If already timed out, don't proceed
                    print(f"    > Skipping {signal_name} for '{name}' due to earlier timeout.")
                    return True
                if (time.time() - game_start_time) > timeout_per_game_seconds:
                    print(f"    > TIMEOUT reached for game '{name}' (>{timeout_per_game_seconds}s) before fetching {signal_name}. Skipping remaining signals for this game.")
                    timed_out_for_game = True
                    return True
                return False

            # 1. Google Trends
            gtrends_keyword = overrides.get('google_trends_keyword', name)
            if not check_timeout("Google Trends"):
                print(f"    > Querying Google Trends for: '{gtrends_keyword}'")
                try:
                    trends_df = self.get_google_trends_interest(
                        keyword=gtrends_keyword,
                        timeframe=google_trends_timeframe
                    )
                    if trends_df is not None:
                        if gtrends_keyword in trends_df.columns:
                            game_signals['google_trends_avg'] = trends_df[gtrends_keyword].mean() if not trends_df.empty else 0
                            print(f"    > Google Trends Avg ({google_trends_timeframe}): {game_signals['google_trends_avg']:.2f}")
                        else:
                            game_signals['google_trends_avg'] = 0
                            print(f"    > Google Trends: Keyword '{gtrends_keyword}' not found in results.")
                    else:
                        game_signals['google_trends_avg'] = None
                        print(f"    > Google Trends: Failed or no data.")
                except Exception as e:
                    print(f"    > Error collecting Google Trends for '{gtrends_keyword}': {e}")
                    game_signals['google_trends_avg'] = None
            else:
                game_signals['google_trends_avg'] = None # Ensure key exists if timed out

            # 2. Reddit Data
            clean_name_for_subreddit = re.sub(r'[^\w]', '', name).lower()
            subreddit_to_query = overrides.get('reddit_subreddit', clean_name_for_subreddit)
            if not check_timeout("Reddit Data"):
                if not subreddit_to_query:
                    print(f"    > Skipping Reddit for '{name}' (could not generate valid default subreddit name).")
                    game_signals['reddit_data'] = None
                else:
                    print(f"    > Querying Reddit subreddit: r/{subreddit_to_query}")
                    try:
                        reddit_data = self.get_reddit_data(
                            subreddit_name=subreddit_to_query,
                            time_filter=reddit_time_filter
                        )
                        game_signals['reddit_data'] = reddit_data
                        if reddit_data and reddit_data.get('subscribers') is not None:
                            print(f"    > Reddit Data (Subscribers: {reddit_data.get('subscribers')}, Active: {reddit_data.get('active_users')}, Posts_{reddit_time_filter}: {reddit_data.get(f'recent_post_count_{reddit_time_filter}')})")
                    except Exception as e:
                        print(f"    > Error collecting Reddit data for r/{subreddit_to_query}: {e}")
                        game_signals['reddit_data'] = None
            else:
                game_signals['reddit_data'] = None # Ensure key exists if timed out

            # 3. Twitter Data
            clean_name_for_hashtag = re.sub(r'[^\w]', '', name)
            default_twitter_query = f'"{name}" OR #{clean_name_for_hashtag}' if clean_name_for_hashtag else f'"{name}"'
            twitter_query_to_use = overrides.get('twitter_query', default_twitter_query)
            if not check_timeout("Twitter Data"):
                print(f"    > Querying Twitter for: {twitter_query_to_use}")
                try:
                    twitter_data = self.get_twitter_data(
                        query=twitter_query_to_use,
                        time_window_minutes=twitter_time_window_minutes
                    )
                    game_signals['twitter_data'] = twitter_data
                    if twitter_data and twitter_data.get('recent_tweet_count') is not None:
                        print(f"    > Twitter Data (Recent Count {twitter_time_window_minutes}m: {twitter_data.get('recent_tweet_count')})")
                except Exception as e:
                    print(f"    > Error collecting Twitter data for query '{twitter_query_to_use}': {e}")
                    game_signals['twitter_data'] = None
            else:
                game_signals['twitter_data'] = None # Ensure key exists if timed out

            # 4. YouTube Data
            default_youtube_query = f'"{name}" official trailer OR gameplay'
            youtube_query_to_use = overrides.get('youtube_query', default_youtube_query)
            if not check_timeout("YouTube Data"):
                print(f"    > Querying YouTube for: {youtube_query_to_use}")
                try:
                    youtube_data = self.get_youtube_data(
                        search_query=youtube_query_to_use,
                        max_results=youtube_max_results
                    )
                    game_signals['youtube_data'] = youtube_data
                except Exception as e:
                    print(f"    > Error collecting YouTube data for query '{youtube_query_to_use}': {e}")
                    game_signals['youtube_data'] = None
            else:
                game_signals['youtube_data'] = None # Ensure key exists if timed out

            external_data[name] = game_signals

        print(f"[{datetime.datetime.now()}] Finished collecting external signals.")
        return external_data

    def get_google_trends_interest(self, keyword: str, timeframe: str = 'today 3-m', geo: str = '', retries: int = 2, delay: int = 15) -> Optional[pd.DataFrame]:
        """
        Fetches Google Trends interest over time for a specific keyword.
        Uses a pre-initialized pytrends client with a shared session.

        Args:
            keyword (str): The search term (e.g., game name) to query.
            timeframe (str): Time range for the data. Examples: 'today 5-y', 'today 3-m', '2024-01-01 2024-04-30'.
                             Defaults to 'today 3-m' (last 3 months).
            geo (str): Geolocation filter (e.g., 'US'). Defaults to worldwide.
            retries (int): Number of retry attempts on rate limit errors (429).
            delay (int): Initial delay in seconds between retries. Increased default to 15.

        Returns:
            Optional[pd.DataFrame]: A pandas DataFrame with the interest scores over time,
                                    or None if pytrends is not installed or an error occurs.
                                    The DataFrame index is datetime, and columns include the keyword score,
                                    and 'isPartial' boolean.
        """
        if not self.pytrends_client: # Check if the client was initialized
            print("Error: Pytrends client not initialized. Cannot fetch Google Trends data.")
            return None

        current_delay = delay
        attempt = 0
        while attempt <= retries:
            try:
                # Use the shared pytrends_client
                self.pytrends_client.build_payload([keyword], cat=0, timeframe=timeframe, geo=geo, gprop='')
                interest_df = self.pytrends_client.interest_over_time()

                # Increase delay slightly after each request to be polite
                time.sleep(5) # Increased base sleep slightly

                if interest_df.empty:
                    print(f"Info: No Google Trends data found for keyword '{keyword}' in timeframe '{timeframe}'.")
                    return interest_df # Return empty DataFrame

                # Drop the 'isPartial' column
                if 'isPartial' in interest_df.columns:
                     interest_df = interest_df.drop(columns=['isPartial'])

                return interest_df # Success

            except Exception as e:
                # Check if it's a rate limit error (often manifests as ResponseError with status 429)
                is_rate_limit = 'response code 429' in str(e).lower()

                if is_rate_limit and attempt < retries:
                    attempt += 1
                    print(f"Warning: Google Trends rate limit hit for '{keyword}'. Retrying ({attempt}/{retries}) after {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= 2 # Exponential backoff
                else:
                    # Log non-retryable errors or final failure
                    if is_rate_limit:
                         print(f"Error: Max retries reached for Google Trends keyword '{keyword}'.")
                    else:
                         print(f"Error fetching Google Trends data for '{keyword}': {e}")
                    return None # Non-retryable error or max retries reached
            except KeyboardInterrupt: # Allow stopping the process
                 print("KeyboardInterrupt received, stopping Google Trends fetch.")
                 raise
            except BaseException as base_e: # Catch broader issues if needed
                 print(f"Unexpected base error fetching Google Trends for '{keyword}': {base_e}")
                 return None
        
        # This part should ideally not be reached if logic above is correct, but as a safeguard:
        print(f"Error: Failed to fetch Google Trends for '{keyword}' after multiple attempts.")
        return None

    def get_reddit_data(self, subreddit_name: str, time_filter: str = 'month') -> Dict:
        """
        Get data for a specific subreddit (subscriber count, active users, recent post count).

        Args:
            subreddit_name (str): The name of the subreddit to query (without 'r/').
            time_filter (str): Time filter for counting recent posts ('hour', 'day', 'week', 'month', 'year', 'all').
                               Defaults to 'month'.

        Returns:
            Dict: A dictionary containing subreddit data like 'subscribers', 'active_users',
                  f'recent_post_count_{time_filter}', or None values if data is unavailable or an error occurs.
        """
        if not self.reddit_client or not prawcore:
            print("Error: Reddit client (PRAW/PRAWCore) not initialized or installed.")
            return {"subscribers": None, "active_users": None, f"recent_post_count_{time_filter}": None}

        # Define default return structure for errors
        error_result = {"subscribers": None, "active_users": None, f"recent_post_count_{time_filter}": None}

        try:
            subreddit = self.reddit_client.subreddit(subreddit_name)
            
            # Access an attribute to trigger potential exceptions like NotFound/Redirect early
            _ = subreddit.display_name 

            # Basic subreddit info
            subscribers = subreddit.subscribers
            # Use getattr for potentially missing attributes like accounts_active
            active_users = getattr(subreddit, 'accounts_active', None) 

            # Count recent posts
            now = int(time.time())
            if time_filter == 'hour': start_time = now - 3600
            elif time_filter == 'day': start_time = now - 86400
            elif time_filter == 'week': start_time = now - 604800
            elif time_filter == 'month': start_time = now - 2592000 # Approx 30 days
            elif time_filter == 'year': start_time = now - 31536000
            else: start_time = 0 # 'all'
            
            # Use Pushshift query format if available/needed, or stick to PRAW search
            # PRAW search might be less reliable for exact counts over specific time ranges
            query = f"timestamp:{start_time}..{now}"
            post_count = 0
            try:
                # Limit search results heavily to avoid excessive API usage/time
                # Note: PRAW search limit is often 1000 max, might not be accurate for high-volume subs
                for _ in subreddit.search(query, syntax='cloudsearch', limit=1000): 
                    post_count += 1
                if post_count == 1000:
                    print(f"Warning: Reached PRAW search limit (1000) for r/{subreddit_name} in time_filter '{time_filter}'. Count may be higher.")
            except prawcore.exceptions.ServerError as search_error: # More specific exception for search issues
                 print(f"Reddit Server Error during search for r/{subreddit_name}: {search_error}")
                 post_count = None # Indicate search failure
            except Exception as search_error:
                 # Catch other errors during the search itself
                 print(f"Error during Reddit search query execution for r/{subreddit_name}: {search_error}")
                 post_count = None # Indicate search failure

            # Increase delay slightly
            time.sleep(1) 

            return {
                "subscribers": subscribers,
                "active_users": active_users,
                f"recent_post_count_{time_filter}": post_count
            }
        # Catch specific prawcore exceptions first
        except prawcore.exceptions.Redirect: # If subreddit is redirected (e.g., capitalization change)
            print(f"Info: Subreddit r/{subreddit_name} is redirected. Consider updating the name.")
            return error_result # Treat as not found for simplicity here
        except prawcore.exceptions.NotFound: # Subreddit does not exist
            print(f"Info: Subreddit r/{subreddit_name} not found.")
            return error_result
        except prawcore.exceptions.Forbidden: # Private subreddit, banned, etc.
            print(f"Info: Access forbidden for subreddit r/{subreddit_name}.")
            return error_result
        except prawcore.exceptions.ResponseException as e:
            # Catch other response-related errors (like 401 Unauthorized)
            print(f"PRAW Response Error fetching Reddit data for r/{subreddit_name}: {e} (Status: {e.response.status_code})")
            if e.response.status_code == 401:
                print("    Hint: Check Reddit API Credentials (client_id, client_secret).")
            return error_result
        except praw.exceptions.PRAWException as e: # Catch other PRAW specific errors (Auth, RateLimit, etc.)
            print(f"PRAW API Error fetching Reddit data for r/{subreddit_name}: {e}")
            return error_result
        except Exception as e: # Catch any other unexpected errors during subreddit access
            print(f"Unexpected error fetching Reddit data for r/{subreddit_name}: {e}")
            # Consider adding a check here for specific error types if needed
            # e.g., if isinstance(e, requests.exceptions.ConnectionError):
            #    print("    Hint: Network connection issue?")
            return error_result

    def get_twitter_data(self, query: str, time_window_minutes: int = 60) -> Dict:
        """
        Get recent tweet count for a specific query using Twitter API v2.
        Includes enhanced rate limit handling.
        """
        if not self.twitter_client:
            print("Error: Twitter client not initialized.")
            return {"recent_tweet_count": None}

        current_time = time.time()
        # Cooldown check: If we were rate-limited, wait for the cooldown period to pass.
        if self.twitter_is_in_cooldown and current_time < self.twitter_cooldown_until:
            wait_time = self.twitter_cooldown_until - current_time
            print(f"    Twitter API is in cooldown due to previous rate limit. Waiting for {wait_time / 60:.1f} more minutes.")
            time.sleep(wait_time)
            self.twitter_is_in_cooldown = False
            print("    Twitter API cooldown finished.")
        elif self.twitter_is_in_cooldown and current_time >= self.twitter_cooldown_until:
            # Cooldown period has naturally passed
            self.twitter_is_in_cooldown = False
            print("    Twitter API cooldown period has passed.")

        # Proactive delay to respect rate limits
        time_since_last_call = current_time - self.twitter_last_api_call_time
        if time_since_last_call < self.twitter_min_interval:
            sleep_duration = self.twitter_min_interval - time_since_last_call
            print(f"    Proactively sleeping for {sleep_duration:.2f}s to respect Twitter rate limits (min interval: {self.twitter_min_interval}s).")
            time.sleep(sleep_duration)

        try:
            self.twitter_last_api_call_time = time.time() # Update timestamp before making the call

            now = datetime.datetime.now(datetime.timezone.utc)
            start_time = now - datetime.timedelta(minutes=time_window_minutes)
            seven_days_ago = now - datetime.timedelta(days=7)
            if start_time < seven_days_ago:
                start_time = seven_days_ago
            
            min_start_time = now - datetime.timedelta(seconds=15) 
            if start_time > min_start_time:
                start_time = min_start_time
                
            start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')

            response = self.twitter_client.get_recent_tweets_count(query=query, start_time=start_time_str)
            
            # Successful call, ensure cooldown flag is false
            self.twitter_is_in_cooldown = False 

            if response and response.meta and 'total_tweet_count' in response.meta:
                return {"recent_tweet_count": response.meta['total_tweet_count']}
            elif response and response.errors:
                 # Log specific errors returned by the API
                 print(f"Error from Twitter API while counting tweets for '{query}': {response.errors}")
                 return {"recent_tweet_count": None}
            else:
                # Handle case where response might be valid but contain no count (e.g., 0 tweets or unexpected meta)
                total_count = response.meta.get('total_tweet_count', 0) if response and response.meta else 0
                # print(f"Info: Found {total_count} tweets for query '{query}' in the specified time window.") # Less verbose
                return {"recent_tweet_count": total_count}

        except tweepy.errors.TooManyRequests as e:
            print(f"Error: Twitter API rate limit exceeded for query '{query}'. {e}.")
            cooldown_duration_minutes = self.twitter_rate_limit_cooldown / 60
            print(f"    Entering a {cooldown_duration_minutes:.1f} minute cooldown period for Twitter API calls.")
            self.twitter_is_in_cooldown = True 
            self.twitter_cooldown_until = time.time() + self.twitter_rate_limit_cooldown
            return {"recent_tweet_count": None}
        except tweepy.errors.TweepyException as e:
            # Handle other potential Tweepy errors (authentication, connection, bad request from query syntax)
            print(f"Tweepy API Error fetching tweet count for '{query}': {e}")
            # Check if it's a bad request potentially due to query syntax
            if isinstance(e, tweepy.errors.BadRequest):
                print(f"    Hint: Check Twitter query syntax for potential issues: {query}")
            # Check for authentication issues (often 401/403)
            if isinstance(e, tweepy.errors.Forbidden) or isinstance(e, tweepy.errors.Unauthorized):
                 print("    Hint: Check Twitter Bearer Token.")
            return {"recent_tweet_count": None}
        except Exception as e:
            # Catch any other unexpected errors
            print(f"Unexpected error fetching Twitter tweet count for '{query}': {e}")
            return {"recent_tweet_count": None}

    def get_youtube_data(self, search_query: str, max_results: int = 5) -> Dict:
        """
        Get basic YouTube video statistics (views, likes) for a given search query.

        Args:
            search_query (str): The query string to search on YouTube.
            max_results (int): The maximum number of search results to process (1-50).

        Returns:
            Dict: A dictionary containing aggregated YouTube data like:
                  'total_views_top_N', 'avg_views_top_N', 'avg_likes_top_N',
                  or None values if data is unavailable or an error occurs.
        """
        if build is None or HttpError is None:
            print("Error: google-api-python-client library not installed.")
            return {"total_views_top_N": None, "avg_views_top_N": None, "avg_likes_top_N": None}

        youtube_config = self.config.get('youtube', {})
        api_key = youtube_config.get('api_key')

        if not api_key:
            print("Error: YouTube API key missing in config/environment.")
            return {"total_views_top_N": None, "avg_views_top_N": None, "avg_likes_top_N": None}

        try:
            youtube = build('youtube', 'v3', developerKey=api_key)
            # Use the provided search_query directly
            print(f"    > YouTube Search Query: {search_query}")

            # 1. Search for videos
            search_response = youtube.search().list(
                q=search_query,
                part='id',
                type='video',
                order='relevance', 
                maxResults=max(1, min(max_results, 50))
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

            if not video_ids:
                print(f"    > No relevant YouTube videos found for query.")
                return {"total_views_top": 0, "avg_views_top": 0, "avg_likes_top": 0}

            # 2. Get statistics for the found video IDs
            video_response = youtube.videos().list(
                part='statistics',
                id=','.join(video_ids)
            ).execute()

            # 3. Aggregate statistics
            total_views = 0
            total_likes = 0
            valid_videos_count = 0

            for item in video_response.get('items', []):
                stats = item.get('statistics', {})
                views = int(stats.get('viewCount', 0))
                likes = int(stats.get('likeCount', 0))
                total_views += views
                total_likes += likes
                valid_videos_count += 1

            avg_views = total_views / valid_videos_count if valid_videos_count > 0 else 0
            avg_likes = total_likes / valid_videos_count if valid_videos_count > 0 else 0

            print(f"    > YouTube Stats (Top {valid_videos_count} videos): Total Views={total_views}, Avg Views={avg_views:.0f}, Avg Likes={avg_likes:.0f}")

            # Use valid_videos_count in the keys
            return {
                f"total_views_top_{valid_videos_count}": total_views,
                f"avg_views_top_{valid_videos_count}": avg_views,
                f"avg_likes_top_{valid_videos_count}": avg_likes
            }

        except HttpError as e:
            print(f"    > YouTube API Error: {e}")
            if e.resp.status == 403:
                 print("    > Potential Quota Exceeded or API Key issue.")
            return {"total_views_top_N": None, "avg_views_top_N": None, "avg_likes_top_N": None}
        except Exception as e:
            print(f"    > Unexpected error fetching YouTube data for query '{search_query}': {e}")
            return {"total_views_top_N": None, "avg_views_top_N": None, "avg_likes_top_N": None}

    def get_twitch_data(self, game_name_or_id: str) -> Dict:
        """
        Get data for game streams on Twitch (e.g., current viewer count, streamer count).
        (Requires Twitch API)
        """
        # --- Implementation Needed ---
        # Use Twitch API library or direct requests
        # Authenticate using client ID and secret
        # Get streams filtered by game
        # Aggregate viewer counts, count active streamers
        # --- End Implementation Needed ---
        print(f"Placeholder: Getting Twitch data for game '{game_name_or_id}'")
        return {"current_viewers": None, "current_streamers": None} # Placeholder

    # Add helper methods for API interaction, parsing, and potentially sentiment analysis