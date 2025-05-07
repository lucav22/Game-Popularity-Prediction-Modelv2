# Game Popularity Prediction Model V2

**Version:** 2.2 (Comprehensive README Update)
**Date:** 2025-05-06

## 1. Project Objective

The primary objective of this project is to develop a data-driven system capable of **predicting the pre-release hype and potential post-launch success** of video games. It aims to quantify pre-release traction using various online metrics and validate these predictions against actual post-launch engagement data. The ultimate goal is to create an automated pipeline that can support machine learning models for forecasting game popularity, moving beyond manual analysis.

## 2. What This Is (High-Level Explanation)

This project is an end-to-end data pipeline and machine learning system designed to:
1.  **Collect** data about video games from multiple online sources (Steam, Twitch, Google Trends, Reddit, Twitter, YouTube).
2.  **Process and Engineer** this raw data into meaningful features that represent game hype and engagement.
3.  **Train and Evaluate** predictive models to forecast game popularity metrics, such as peak player counts.

It serves as a proof-of-concept for leveraging publicly available data to gain insights into the video game market.

## 3. How It Works (The Pipeline)

The system operates in three main stages, primarily orchestrated through Jupyter Notebooks and Python scripts:

### 3.1. Data Collection
*   **Key Components:**
    *   `notebooks/01_data_collection.ipynb`: Orchestrates the data collection process.
    *   `src/data_collector.py` (`DataCollector` class): Manages API interactions and data aggregation.
    *   `src/connectors/`: Contains individual connector classes for different APIs:
        *   `steam_api_connector.py` (`SteamAPIConnector`): Fetches game details (name, release date, Metacritic score, genres, price) and player counts from Steam.
        *   `twitch_api_connector.py` (`TwitchAPIConnector`): Fetches live viewership statistics from Twitch.
        *   `external_data_collector.py` (`ExternalDataCollector`): Gathers data from Google Trends (search interest), Reddit (subreddit activity, subscriber counts), Twitter (tweet volumes), and YouTube (video statistics like views and likes).
*   **Process:**
    1.  The `DataCollector` is initialized with a list of game App IDs, categorized for analysis (e.g., "successful", "declining", "experimental").
    2.  It uses the respective API connectors to fetch data for each game.
    3.  Game names obtained from Steam are used to query Twitch and external platforms. The `external_platform_mapping` in `DataCollector` helps refine queries for specific games.
*   **Output:**
    *   Raw, timestamped data snapshots are saved as compressed CSV files (e.g., `data/steam_data_YYYY-MM-DD-HH-MM.csv.gz`). Each file contains the collected metrics for the tracked games at a specific point in time.

### 3.2. Feature Engineering
*   **Key Components:**
    *   `notebooks/02_feature_engineering.ipynb`: Manages the feature engineering workflow.
    *   `src/aggregator.py` (`DataAggregator` class): Consolidates raw data and computes aggregated features.
*   **Process:**
    1.  The `DataAggregator` loads and merges all individual raw data files from the `data/` directory.
    2.  It cleans the data and converts necessary columns to appropriate types (e.g., `timestamp`, `release_date` to datetime objects).
    3.  For each game, it uses the `release_date` as a reference to calculate:
        *   **Pre-release features:** Aggregated metrics from a defined window *before* the game's launch (e.g., average Google Trends score 30 days pre-launch, Reddit subscriber count just before release).
        *   **Post-launch outcome metrics:** Aggregated or peak metrics from defined windows *after* the game's launch (e.g., peak Steam player count in the first 7 days, average Twitch viewers over 30 days).
*   **Output:**
    *   A single, consolidated CSV file: `data/aggregated_game_features.csv`. Each row in this file represents a unique game, and columns contain static game information, engineered pre-release features, and post-launch outcome metrics.

### 3.3. Predictive Modeling
*   **Key Components:**
    *   `notebooks/03_predictive_modeling.ipynb`: Contains the workflow for training and evaluating predictive models.
*   **Process:**
    1.  Loads the `aggregated_game_features.csv` dataset.
    2.  **Data Preparation:**
        *   Defines the feature set (X) – typically pre-release metrics and static game info.
        *   Defines the target variable (y) – a post-launch success metric (e.g., `steam_peak_players_7d`).
        *   Handles missing values (e.g., dropping rows with missing target, imputing feature NaNs).
        *   Splits the data into training and testing sets.
        *   Applies feature scaling (e.g., `StandardScaler`) to numerical features.
    3.  **Model Training:** Trains several regression algorithms (e.g., Linear Regression, Random Forest Regressor, Gradient Boosting Regressor) on the prepared training data.
    4.  **Model Evaluation:** Evaluates each trained model on the unseen test data using metrics such as Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and R-squared (R²).
    5.  **Comparison & Analysis:** Compares model performances and analyzes feature importances (for tree-based models).
*   **Output:**
    *   Performance metrics for each model.
    *   Visualizations of model comparisons and feature importances.
    *   Optionally, the best-performing model and its associated scaler can be saved (e.g., using `joblib`) for future use.

## 4. The Reason (Project Rationale)

The video game industry is dynamic and competitive. Understanding what drives a game's popularity can be invaluable for developers, publishers, and market analysts. This project aims to:
*   **Automate Insights:** Provide an automated, data-driven approach to assess a game's potential before and after its release, reducing reliance on manual research and intuition.
*   **Quantify Hype:** Develop quantitative measures of pre-release excitement and community engagement.
*   **Predict Success:** Build models that can forecast key success indicators, such as player engagement, based on early signals.
*   **Educational Tool:** Serve as a practical example of an end-to-end data science project, encompassing data collection, feature engineering, and machine learning.

## 5. System Architecture

The project is structured as follows:

```
game-popularity-predictor-v2/
├── data/                             # Stores collected raw data and aggregated features
│   ├── aggregated_game_features.csv
│   └── steam_data_*.csv.gz
├── docs/                             # (Optional, for detailed documentation)
├── models/                           # (Optional, for saved trained models)
├── notebooks/                        # Jupyter notebooks for different pipeline stages
│   ├── 01_data_collection.ipynb
│   ├── 02_feature_engineering.ipynb
│   └── 03_predictive_modeling.ipynb
├── src/                              # Source code for core logic
│   ├── __init__.py
│   ├── aggregator.py                 # Data aggregation logic
│   ├── data_collector.py             # Data collection orchestration
│   ├── utils.py                      # Utility functions
│   └── connectors/                   # API connector modules
│       ├── __init__.py
│       ├── external_data_collector.py
│       ├── steam_api_connector.py
│       └── twitch_api_connector.py
├── tests/                            # Unit and integration tests
│   ├── __init__.py
│   └── ...
├── .env                              # For API keys and environment variables (MUST BE CREATED)
├── .gitignore
├── README.md
└── requirements.txt                  # Python dependencies
```

## 6. Data Schema (Key Features & Outcomes)

The system collects a variety of data points, which are then engineered into features.

**Key Raw Data Points Collected:**
*   **Steam:** Game Name, App ID, Release Date, Metacritic Score, Genres, Price, Player Counts.
*   **Twitch:** Game Viewership Counts.
*   **Google Trends:** Relative Search Interest Over Time.
*   **Reddit:** Subreddit Subscribers, Active Users, Recent Post Counts.
*   **Twitter:** Recent Tweet Counts for specific queries.
*   **YouTube:** Video Views and Likes for top search results.

**Engineered Pre-Release Features (Examples from `aggregated_game_features.csv`):**
*   `metacritic_score`: Metacritic score.
*   `google_trends_avg_pre`: Average Google Trends score in a window before release (e.g., 30 days).
*   `reddit_posts_avg_pre`: Average number of Reddit posts in a window before release.
*   `twitter_count_avg_pre`: Average Twitter mention count in a window before release.
*   `reddit_subs_pre`: Number of Reddit subscribers for the game's subreddit just before release.
*   `reddit_active_pre`: Number of active users on the game's subreddit just before release.
*   `youtube_total_views_pre`: Total YouTube views for relevant videos before release.
*   `youtube_avg_likes_pre`: Average YouTube likes for relevant videos before release.

**Engineered Post-Launch Outcomes/Target Variables (Examples):**
*   `steam_peak_players_7d`: Peak concurrent Steam players within the first 7 days of launch.
*   `twitch_peak_viewers_7d`: Peak Twitch viewers within the first 7 days of launch.
*   `steam_avg_players_30d`: Average Steam players over the first 30 days of launch.
*   `twitch_avg_viewers_30d`: Average Twitch viewers over the first 30 days of launch.

## 7. Setup and Usage

### Prerequisites
*   Python (3.9+ recommended)
*   pip (Python package installer)
*   Git

### Setup Instructions
1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd game-popularity-prediction-modelv2
    ```
2.  **Create and Activate a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\\Scripts\\activate
    # On macOS/Linux
    source venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set Up API Keys (.env file):**
    Create a file named `.env` in the root directory of the project (`game-popularity-prediction-modelv2/.env`). Add your API keys and other necessary credentials to this file. The `src/connectors/external_data_collector.py` and other connectors will load these.

    Example `.env` content:
    ```env
    STEAM_API_KEY="YOUR_STEAM_API_KEY"
    TWITCH_CLIENT_ID="YOUR_TWITCH_CLIENT_ID"
    TWITCH_CLIENT_SECRET="YOUR_TWITCH_CLIENT_SECRET"
    REDDIT_CLIENT_ID="YOUR_REDDIT_CLIENT_ID"
    REDDIT_CLIENT_SECRET="YOUR_REDDIT_CLIENT_SECRET"
    REDDIT_USER_AGENT="YOUR_REDDIT_USER_AGENT" # e.g., "GamePopularityBot/0.1 by YourUsername"
    TWITTER_BEARER_TOKEN="YOUR_TWITTER_BEARER_TOKEN"
    YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY"
    ```
    *   **Note:** Ensure the `.env` file is added to your `.gitignore` if it's not already, to prevent committing your secret keys.

### Running the Pipeline
Execute the Jupyter Notebooks in the `notebooks/` directory in the following order:

1.  **`01_data_collection.ipynb`**:
    *   This notebook runs the `DataCollector` to fetch current data from all configured sources.
    *   It saves the output to a timestamped `.csv.gz` file in the `data/` directory.
    *   This notebook can be run periodically (e.g., daily, weekly) to build up a historical dataset.
2.  **`02_feature_engineering.ipynb`**:
    *   This notebook uses the `DataAggregator` to load all raw data files collected by the first notebook.
    *   It processes this data to create the `aggregated_game_features.csv` file, which contains one row per game with engineered pre-release and post-launch features.
3.  **`03_predictive_modeling.ipynb`**:
    *   This notebook loads `aggregated_game_features.csv`.
    *   It then proceeds with training various machine learning models to predict a chosen target variable (e.g., `steam_peak_players_7d`).
    *   It evaluates model performance and provides insights into feature importance.

## 8. Key Technologies and Libraries

*   **Programming Language:** Python
*   **Data Handling & Analysis:** Pandas, NumPy
*   **Machine Learning:** Scikit-learn
*   **API Interaction:**
    *   Requests (general HTTP)
    *   PRAW (Reddit API Wrapper)
    *   Tweepy (Twitter API v2 Wrapper)
    *   Pytrends (Google Trends unofficial API)
    *   google-api-python-client (YouTube API)
*   **Development Environment:** Jupyter Notebooks, Visual Studio Code
*   **Environment Management:** `venv`
*   **Configuration:** `python-dotenv` (for `.env` files)

## 9. Future Enhancements

Based on the project's current state and findings (especially from `03_predictive_modeling.ipynb`), potential future enhancements include:

*   **Hyperparameter Optimization:** Systematically tune the hyperparameters of the best-performing models (e.g., using GridSearchCV or RandomizedSearchCV).
*   **Advanced Feature Engineering:**
    *   Explore interaction terms between existing features.
    *   Develop more sophisticated temporal features (e.g., growth rates of metrics).
    *   Incorporate sentiment analysis from text data (Reddit comments, tweets).
*   **Algorithm Exploration:** Experiment with a broader range of models, including XGBoost, LightGBM, CatBoost, or neural networks.
*   **Data Expansion:**
    *   Collect data at a higher frequency if APIs permit.
    *   Integrate data from other platforms (e.g., Discord, gaming news sites).
    *   Include more detailed game characteristics (e.g., developer/publisher reputation scores, marketing budget indicators if obtainable).
*   **Increased Data Volume:** Continuously run the data collection pipeline to build a larger historical dataset for more robust model training.
*   **Deployment & Monitoring:** Package the best model into an API and implement a system to monitor its performance on new games over time, triggering retraining as needed.
*   **Refined External Data Mapping:** Continuously improve the `external_platform_mapping` in `DataCollector` for more accurate querying of external platforms.