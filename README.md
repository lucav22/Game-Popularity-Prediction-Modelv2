# Game Popularity Prediction Model V2

**Version:** 2.1 (Twitch Connector Added, Focus Shifted)
**Date:** 2025-05-04

## 1. Project Objective

To develop a system that **predicts the pre-release hype and potential post-launch success** of video games. The primary goal is to quantify pre-release traction (using metrics like social media volume, search trends) and validate these predictions against actual post-launch engagement data (player counts, viewership). The system aims to replace manual analysis with a robust, automated pipeline suitable for machine learning.

## 2. Current Status & Key Features Implemented

*   **Steam API Integration:** Real-time data access using `src.connectors.steam_api_connector.SteamAPIConnector` for post-launch player counts and game details.
*   **Twitch API Integration:** Real-time data access using `src.connectors.twitch_api_connector.TwitchAPIConnector` for post-launch viewership data.
*   **Data Collection Pipeline:** Managed by `src.data_collector.DataCollector` (currently focused on Steam, needs integration for Twitch and external sources).
*   **Initial Feature Engineering & Utils:** Basic functions in `src.feature_engineering.py` and `src.utils.py`.
*   **Analysis & Testing:**
    *   Notebooks (`01_data_collection.ipynb`, `02_feature_engineering.ipynb`) for demonstrating workflows.
    *   `tests/` directory structure is in place.
*   **External Data Collection (In Progress):** `src.connectors.external_data_collector.py` is being developed to gather pre-release signals like Google Trends and Reddit activity.

## 3. System Architecture

game-popularity-predictor-v2/
├── data/
├── docs/
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_feature_engineering.ipynb
│   └── 03_modeling.ipynb     # (Planned - Focus on Hype Prediction & Validation)
├── src/
│   ├── __init__.py
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── steam_api_connector.py
│   │   ├── twitch_api_connector.py
│   │   ├── external_data_collector.py # (In Progress - Google Trends, Reddit)
│   │   └── epic_api_connector.py     # (Shelved - API/Scraping challenges)
│   ├── aggregator.py         # (Planned) Handles data unification
│   ├── data_collector.py     # Orchestrates data collection
│   ├── feature_engineering.py# Feature calculation (pre & post-release)
│   └── utils.py              # Helper functions
├── tests/
│   ├── __init__.py
│   └── # (Mirrors src structure)
├── venv/
├── .gitignore
├── README.md
└── requirements.txt

## 4. Data Schema (Target - Focused on Prediction & Validation)

The goal is to collect pre-release indicators and link them to post-launch outcomes.

**Pre-Release Features (Examples):**
*   `google_trends_score (pre-launch)`: Relative search interest before release.
*   `reddit_mention_volume (pre-launch)`: Activity in relevant subreddits.
*   `twitter_mention_volume (pre-launch)`: (If feasible)
*   `developer_reputation_score`: Based on past performance.
*   `genre_popularity_index`: Based on recent trends.
*   `is_sequel_or_ip`: Boolean.

**Post-Launch Validation Metrics (Examples):**
*   `steam_peak_players_week1`: Peak concurrent players in first 7 days.
*   `steam_avg_players_month1`: Average players over first 30 days.
*   `twitch_peak_viewers_week1`: Peak viewers in first 7 days.
*   `twitch_avg_viewers_month1`: Average viewers over first 30 days.
*   `post_launch_social_volume`: Ongoing discussion volume.

**Unified Structure (Conceptual):**
```json
{
  "game_identifier": "unique_game_id",
  "game_name": "str",
  "release_date": "datetime",
  // --- Pre-Release Features ---
  "pre_release_google_trend": "float",
  "pre_release_reddit_volume": "int",
  // ... other pre-release features ...
  // --- Post-Launch Outcomes (Collected after release for training/validation) ---
  "post_launch_steam_peak_wk1": "int",
  "post_launch_twitch_peak_wk1": "int",
  // ... other post-launch metrics ...
}
```