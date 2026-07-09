import importlib
from pathlib import Path
import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from PIL import Image, ImageDraw

import utils.ai_report as scouting_report_helpers

scouting_report_helpers = importlib.reload(scouting_report_helpers)


# This file was created in Milestone 7.
# It already includes clean stats, percentiles, strengths, and weaknesses.
DATA_FILE_PATH = "cleaned_data/skaters_strengths.csv"
NHL_EDGE_BASE_URL = "https://api-web.nhle.com/v1/edge"
MICROSTATS_FILE_PATH = "data/all_three_zones_2025_26_regular.csv"
MINIMUM_GAMES_FOR_IMPACT = 10
FULL_TRUST_GAMES = 25
SMALL_SAMPLE_TRUST = 0.65
SPECIAL_TEAMS_TOI_MINIMUM = 0.75
LIMITED_SPECIAL_TEAMS_OVERALL_SCORE = 45


def add_custom_styles():
    """
    Add a few small visual tweaks to the Streamlit page.
    """
    st.markdown(
        """
        <style>
        div[data-testid="stExpander"] summary p {
            font-size: 1.08rem;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalize_name(name):
    """
    Normalize player names so different data sources can match.

    Example:
    "Brad\u00a0Marchand" and "Brad Marchand" become the same key.
    """
    name = str(name).replace("\u00a0", " ")
    name = re.sub(r"[^a-zA-Z ]", "", name)
    name = re.sub(r"\s+", " ", name).strip().lower()

    return name


def load_player_data():
    """
    Load the prepared player-card dataset.
    """
    player_data = pd.read_csv(DATA_FILE_PATH)
    return player_data


@st.cache_data
def load_microstats_data():
    """
    Load the summarized All Three Zones microstats file.
    """
    microstats_path = Path(MICROSTATS_FILE_PATH)

    if not microstats_path.exists():
        return None

    microstats_data = pd.read_csv(microstats_path)
    microstats_data["name_key"] = microstats_data["Player"].apply(normalize_name)

    return microstats_data


@st.cache_data(ttl=3600)
def load_nhl_edge_data(player_id):
    """
    Load NHL EDGE tracking data for one player.

    NHL EDGE data comes from the NHL's public web API.
    ttl=3600 means Streamlit can reuse the result for one hour.
    """
    edge_url = f"{NHL_EDGE_BASE_URL}/skater-detail/{player_id}/now"

    try:
        response = requests.get(edge_url, timeout=10)

        if response.status_code == 200:
            return response.json()

    except requests.RequestException:
        pass

    return None


def show_stat(label, value):
    """
    Show one stat using Streamlit's metric display.

    label is the stat name.
    value is the number shown on the card.
    """
    st.metric(label=label, value=value)


def format_optional_minutes(value):
    """
    Format TOI per game.

    If the player did not play that situation, show NA.
    """
    if pd.isna(value):
        return "NA"

    return f"{round(value, 2)}"


def format_optional_number(value, decimals=0):
    """
    Format an optional stat.

    Missing values show as NA.
    """
    if pd.isna(value):
        return "NA"

    if decimals == 0:
        return int(value)

    return round(value, decimals)


def format_optional_percentage(value):
    """
    Format a decimal percentage.

    Example:
    0.563 becomes 56.3%.
    """
    if pd.isna(value):
        return "NA"

    return f"{round(value * 100, 1)}%"


def format_edge_number(value, decimals=1):
    """
    Format a number from NHL EDGE.
    """
    if value is None or pd.isna(value):
        return "NA"

    return round(value, decimals)


def format_edge_percentile(value):
    """
    Format an NHL EDGE percentile.

    NHL EDGE percentiles arrive as decimals:
    0.85 means 85th percentile.
    """
    if value is None or pd.isna(value):
        return "NA"

    return f"{round(value * 100)}th"


def get_nested_value(data, keys):
    """
    Safely get a value from nested NHL EDGE data.

    Example:
    get_nested_value(data, ["skatingSpeed", "speedMax", "imperial"])
    """
    current_value = data

    for key in keys:
        if not isinstance(current_value, dict) or key not in current_value:
            return None

        current_value = current_value[key]

    return current_value


def get_shot_location_summary(edge_data, location_code):
    """
    Find one shot-location row from NHL EDGE.

    Common location codes are:
    - all
    - high
    - mid
    - long
    """
    shot_summary = edge_data.get("sogSummary", [])

    for location_summary in shot_summary:
        if location_summary.get("locationCode") == location_code:
            return location_summary

    return {}


def safe_micro_value(row, column_name):
    """
    Get one microstat number from a row.
    """
    if row is None or column_name not in row:
        return 0

    value = row[column_name]

    if pd.isna(value):
        return 0

    return value


def calculate_micro_per_60(row, column_name):
    """
    Convert a microstat count into a per-60 rate.
    """
    toi = safe_micro_value(row, "5v5 TOI")

    if toi <= 0:
        return "NA"

    value = safe_micro_value(row, column_name)

    return round(value / toi * 60, 2)


def calculate_micro_percentage(row, numerator_column, denominator_column):
    """
    Calculate a microstat percentage.
    """
    numerator = safe_micro_value(row, numerator_column)
    denominator = safe_micro_value(row, denominator_column)

    if denominator <= 0:
        return "NA"

    return f"{round(numerator / denominator * 100, 1)}%"


def get_micro_position_group(position):
    """
    Convert a microstats position into a comparison group.
    """
    if position == "D":
        return "D"

    return "F"


def get_micro_comparison_data(row):
    """
    Filter microstats so defensemen compare to defensemen and forwards compare to forwards.
    """
    microstats_data = load_microstats_data()

    if microstats_data is None:
        return None

    position_group = get_micro_position_group(row["Pos."])
    comparison_data = microstats_data[
        microstats_data["Pos."].apply(get_micro_position_group) == position_group
    ]

    return comparison_data


def get_micro_rate_percentile(row, column_name, higher_is_better=True):
    """
    Rank one player's microstat per-60 rate against the microstats file.
    """
    microstats_data = get_micro_comparison_data(row)

    if microstats_data is None or column_name not in microstats_data.columns:
        return None

    value = calculate_micro_per_60(row, column_name)

    if value == "NA":
        return None

    rates = microstats_data[column_name] / microstats_data["5v5 TOI"] * 60

    return calculate_series_percentile(rates, value, higher_is_better)


def get_micro_percentage_percentile(row, numerator_column, denominator_column, higher_is_better=True):
    """
    Rank one player's microstat percentage against the microstats file.
    """
    microstats_data = get_micro_comparison_data(row)

    if (
        microstats_data is None
        or numerator_column not in microstats_data.columns
        or denominator_column not in microstats_data.columns
    ):
        return None

    numerator = safe_micro_value(row, numerator_column)
    denominator = safe_micro_value(row, denominator_column)

    if denominator <= 0:
        return None

    value = numerator / denominator
    percentages = microstats_data[numerator_column] / microstats_data[denominator_column]

    return calculate_series_percentile(percentages, value, higher_is_better)


def get_microstats_row(player):
    """
    Find the selected player's All Three Zones microstats row.
    """
    microstats_data = load_microstats_data()

    if microstats_data is None:
        return None

    player_name_key = normalize_name(player["name"])
    matching_rows = microstats_data[microstats_data["name_key"] == player_name_key]

    if matching_rows.empty:
        return None

    same_team_rows = matching_rows[matching_rows["Team"] == player["team"]]

    if not same_team_rows.empty:
        return same_team_rows.iloc[0]

    return matching_rows.iloc[0]


def format_comparison_value(value, value_type, decimals=2):
    """
    Format one value for the comparison table.

    value_type tells us whether the stat is a number or a percentage.
    """
    if pd.isna(value):
        return "NA"

    if value_type == "percentage":
        return format_optional_percentage(value)

    return round(value, decimals)


def format_season_range(season):
    """
    Format a season as a readable range.

    Example:
    2025 becomes 2025-2026.
    """
    season_start = int(season)
    season_end = season_start + 1

    return f"{season_start}-{season_end}"


def get_percentile_color(value):
    """
    Choose a color based on the percentile value.
    """
    if value >= 95:
        return "#006400"

    if value >= 85:
        return "#1f8f3a"

    if value >= 70:
        return "#8fd14f"

    if value >= 50:
        return "#ffd84d"

    if value >= 35:
        return "#f28c28"

    return "#d62828"


def format_percentile_label(percentile):
    """
    Format a percentile as readable text.
    """
    if percentile is None or pd.isna(percentile):
        return "No ranking"

    return f"{round(percentile)}th percentile"


def show_quality_indicator(percentile):
    """
    Show a small colored label that explains how good a stat is.
    """
    if percentile is None or pd.isna(percentile):
        st.caption("No ranking")
        return

    percentile = round(percentile)
    color = get_percentile_color(percentile)

    st.markdown(
        f"""
        <div style="
            display: inline-block;
            margin-top: -8px;
            margin-bottom: 12px;
            padding: 3px 9px;
            border-radius: 999px;
            background-color: {color};
            color: white;
            font-size: 0.78rem;
            font-weight: 700;">
            {percentile}th percentile
        </div>
        """,
        unsafe_allow_html=True,
    )


def edge_percentile_to_100(edge_percentile):
    """
    Convert NHL EDGE percentile format into our 0-100 format.
    """
    if edge_percentile is None or pd.isna(edge_percentile):
        return None

    return edge_percentile * 100


def calculate_series_percentile(series, value, higher_is_better=True):
    """
    Calculate where one value ranks inside a group of numbers.

    If lower_is_better, we flip the percentile so lower values get better colors.
    """
    if value is None or pd.isna(value):
        return None

    clean_series = pd.to_numeric(series, errors="coerce").dropna()

    if clean_series.empty:
        return None

    percentile = (clean_series <= value).mean() * 100

    if not higher_is_better:
        percentile = 100 - percentile

    return percentile


def calculate_player_data_percentile(player_data, column_name, player, higher_is_better=True):
    """
    Rank one player against players in the same position group.
    """
    if column_name not in player_data.columns or column_name not in player:
        return None

    if player.get("games_played", 0) < MINIMUM_GAMES_FOR_IMPACT:
        return None

    player_value = player[column_name]
    comparison_data = player_data[
        (player_data["position_group"] == player["position_group"])
        & (player_data["games_played"] >= MINIMUM_GAMES_FOR_IMPACT)
    ]

    return calculate_series_percentile(
        comparison_data[column_name],
        player_value,
        higher_is_better,
    )


def show_percentile(label, value):
    """
    Show one percentile as a colored progress bar.

    A percentile is a number from 0 to 100.
    """
    percentile_value = int(value)
    bar_color = get_percentile_color(percentile_value)

    st.markdown(
        f"""
        <div style="margin-bottom: 18px;">
            <div style="font-weight: 600; margin-bottom: 4px;">
                {label}: {percentile_value}th percentile
            </div>
            <div style="height: 18px; background-color: #e8e8e8; border-radius: 9px; overflow: hidden;">
                <div style="height: 18px; width: {percentile_value}%; background-color: {bar_color}; border-radius: 9px;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_position(position):
    """
    Convert MoneyPuck position labels into hockey card labels.
    """
    position_labels = {
        "L": "LW",
        "R": "RW",
        "C": "C",
        "D": "D",
    }

    return position_labels.get(position, position)


def get_player_label(player):
    """
    Create a readable player label for dropdown menus.

    The team and position help us tell players apart.
    """
    position = format_position(player["position"])

    return f"{player['name']} ({player['team']} - {position})"


def get_team_logo_url(team):
    """
    Build the NHL logo URL for a team abbreviation.

    Example:
    TOR becomes https://assets.nhle.com/logos/nhl/svg/TOR_light.svg
    """
    return f"https://assets.nhle.com/logos/nhl/svg/{team}_light.svg"


def get_player_id(player):
    """
    Get the NHL player ID as a whole number.
    """
    return int(player["playerId"])


def get_player_api_url(player):
    """
    Build the NHL API URL for one player.

    The API usually includes an official headshot URL.
    """
    player_id = get_player_id(player)

    return f"https://api-web.nhle.com/v1/player/{player_id}/landing"


def get_latest_team_headshot_url(player):
    """
    Build the newest NHL headshot URL using team and player ID.
    """
    player_id = get_player_id(player)
    team = player["team"]

    return f"https://assets.nhle.com/mugs/nhl/latest/{team}/{player_id}.png"


def get_latest_headshot_url(player):
    """
    Build the newest NHL headshot URL using only player ID.
    """
    player_id = get_player_id(player)

    return f"https://assets.nhle.com/mugs/nhl/latest/{player_id}.png"


def create_blank_headshot():
    """
    Create a simple blank headshot placeholder image.
    """
    image = Image.new("RGB", (220, 220), "#f2f4f7")
    drawing = ImageDraw.Draw(image)

    drawing.ellipse((68, 34, 152, 118), fill="#c7cdd6")
    drawing.pieslice((42, 110, 178, 246), 180, 360, fill="#c7cdd6")
    drawing.ellipse((7, 7, 213, 213), outline="#d9dee7", width=8)

    return image


def get_official_headshot_url(player):
    """
    Ask the NHL API for the player's official headshot URL.
    """
    player_api_url = get_player_api_url(player)

    try:
        response = requests.get(player_api_url, timeout=5)

        if response.status_code == 200:
            player_api_data = response.json()
            return player_api_data.get("headshot")

    except requests.RequestException:
        pass

    return None


def image_url_works(image_url):
    """
    Check whether an image URL actually returns an image.
    """
    try:
        response = requests.get(image_url, timeout=5)
        content_type = response.headers.get("content-type", "")

        return response.status_code == 200 and "image" in content_type

    except requests.RequestException:
        return False


def load_headshot_or_blank(player):
    """
    Load a player headshot.

    If the NHL image is missing, show a blank placeholder instead.
    """
    possible_headshot_urls = [
        get_latest_headshot_url(player),
        get_latest_team_headshot_url(player),
        get_official_headshot_url(player),
    ]

    for headshot_url in possible_headshot_urls:
        if headshot_url and image_url_works(headshot_url):
            return headshot_url

    return create_blank_headshot()


def get_selected_player(player_data):
    """
    Ask the user to choose a season, team, and player.

    Streamlit reruns the script each time a dropdown changes.
    """
    seasons = sorted(player_data["season"].unique())
    season_labels = {format_season_range(season): season for season in seasons}
    selected_season_label = st.selectbox("Choose a season", list(season_labels.keys()))
    selected_season = season_labels[selected_season_label]

    season_data = player_data[player_data["season"] == selected_season]

    teams = sorted(season_data["team"].unique())
    selected_team = st.selectbox("Choose a team", teams)

    team_data = season_data[season_data["team"] == selected_team]

    players = sorted(team_data["name"].unique())
    selected_player_name = st.selectbox("Choose a player", players)

    selected_player_rows = team_data[team_data["name"] == selected_player_name]
    selected_player = selected_player_rows.iloc[0]

    return selected_player


def show_player_header(player):
    """
    Show the top part of the player card.
    """
    position = format_position(player["position"])
    team_logo_url = get_team_logo_url(player["team"])

    headshot_column, logo_column, text_column = st.columns([1, 1, 5])

    with headshot_column:
        headshot_image = load_headshot_or_blank(player)
        st.image(headshot_image, width=120)

    with logo_column:
        st.image(team_logo_url, width=120)

    with text_column:
        st.title(player["name"])
        season_range = format_season_range(player["season"])
        st.subheader(f"{player['team']} | {position} | {season_range}")


def show_basic_stats(player):
    """
    Show simple counting stats.
    """
    st.header("Individual Stats")

    stat_columns = st.columns(5)

    with stat_columns[0]:
        show_stat("Games", int(player["games_played"]))
        show_stat("TOI/G", format_optional_minutes(player.get("total_toi_per_game", pd.NA)))

    with stat_columns[1]:
        show_stat("Goals", format_optional_number(player.get("total_goals", player["I_F_goals"])))
        show_stat("Points", format_optional_number(player.get("total_points", player["I_F_points"])))

    with stat_columns[2]:
        show_stat("Shots", format_optional_number(player.get("total_shots", player["I_F_shotsOnGoal"])))
        on_ice_xg_percentage = round(player["onIce_xGoalsPercentage"] * 100, 1)
        show_stat("5v5 On-Ice xG%", f"{on_ice_xg_percentage}%")

    with stat_columns[3]:
        show_stat("Hits", format_optional_number(player.get("total_hits", player["I_F_hits"])))
        show_stat("Takeaways", format_optional_number(player.get("total_takeaways", player["I_F_takeaways"])))

    with stat_columns[4]:
        show_stat("Blocks", format_optional_number(player.get("total_blocks", player["shotsBlockedByPlayer"])))


def average_percentiles(percentiles):
    """
    Average percentile values while ignoring missing values.

    This lets us build one simple score from several smaller rankings.
    """
    clean_percentiles = [
        percentile
        for percentile in percentiles
        if percentile is not None and not pd.isna(percentile)
    ]

    if len(clean_percentiles) == 0:
        return None

    return sum(clean_percentiles) / len(clean_percentiles)


def weighted_average_percentiles(weighted_percentiles):
    """
    Average percentile values using weights.

    Each item is:
    (percentile_value, weight)

    If one stat is missing, its weight is ignored instead of counting as zero.
    """
    total_weighted_score = 0
    total_weight = 0

    for percentile, weight in weighted_percentiles:
        if percentile is None or pd.isna(percentile):
            continue

        total_weighted_score += percentile * weight
        total_weight += weight

    if total_weight == 0:
        return None

    return total_weighted_score / total_weight


def clamp_score(score):
    """
    Keep an impact score between 0 and 100.
    """
    if score is None or pd.isna(score):
        return None

    return max(0, min(100, score))


def adjust_score_for_usage(raw_score, usage_percentile, low_usage_trust, high_usage_trust):
    """
    Adjust a score based on how much the player is trusted by usage.

    A low-minute player gets pulled toward 50.
    A high-minute player gets pushed slightly farther from 50.
    """
    if raw_score is None or pd.isna(raw_score):
        return None

    if usage_percentile is None or pd.isna(usage_percentile):
        return raw_score

    usage_trust = low_usage_trust + (usage_percentile / 100) * (
        high_usage_trust - low_usage_trust
    )
    adjusted_score = 50 + (raw_score - 50) * usage_trust

    return clamp_score(adjusted_score)


def shrink_score_toward_average(score, trust_factor):
    """
    Pull a small-sample score closer to 50.
    """
    if score is None or pd.isna(score):
        return None

    return clamp_score(50 + (score - 50) * trust_factor)


def add_defensive_usage_boost(defensive_score, total_toi_percentile):
    """
    Give a small defensive boost to players trusted with heavier minutes.
    """
    if defensive_score is None or pd.isna(defensive_score):
        return None

    if total_toi_percentile is None or pd.isna(total_toi_percentile):
        return defensive_score

    if total_toi_percentile >= 85:
        return clamp_score(defensive_score + 5)

    if total_toi_percentile >= 70:
        return clamp_score(defensive_score + 3)

    if total_toi_percentile >= 55:
        return clamp_score(defensive_score + 1)

    return defensive_score


def get_player_percentile(player_data, player, column_name, higher_is_better=True):
    """
    Get one same-position percentile for the selected player.
    """
    return calculate_player_data_percentile(
        player_data,
        column_name,
        player,
        higher_is_better,
    )


def get_special_teams_toi_percentile(player_data, player):
    """
    Rank a player's combined PP and PK ice time against the same position group.
    """
    if player.get("games_played", 0) < MINIMUM_GAMES_FOR_IMPACT:
        return None

    comparison_data = player_data[
        (player_data["position_group"] == player["position_group"])
        & (player_data["games_played"] >= MINIMUM_GAMES_FOR_IMPACT)
    ].copy()

    comparison_data["special_teams_toi_per_game"] = (
        comparison_data["pp_toi_per_game"].fillna(0)
        + comparison_data["pk_toi_per_game"].fillna(0)
    )
    player_special_teams_toi = (
        0 if pd.isna(player.get("pp_toi_per_game", pd.NA)) else player.get("pp_toi_per_game", 0)
    ) + (
        0 if pd.isna(player.get("pk_toi_per_game", pd.NA)) else player.get("pk_toi_per_game", 0)
    )

    return calculate_series_percentile(
        comparison_data["special_teams_toi_per_game"],
        player_special_teams_toi,
    )


def get_special_teams_toi_per_game(player):
    """
    Add PP and PK ice time per game together.
    """
    pp_toi = player.get("pp_toi_per_game", 0)
    pk_toi = player.get("pk_toi_per_game", 0)

    if pd.isna(pp_toi):
        pp_toi = 0

    if pd.isna(pk_toi):
        pk_toi = 0

    return pp_toi + pk_toi


def calculate_impact_scores(player, player_data):
    """
    Create simple impact scores from existing percentiles.

    These are not WAR. They are beginner-friendly value scores built from
    same-position percentiles.
    """
    if player.get("games_played", 0) < MINIMUM_GAMES_FOR_IMPACT:
        return {
            "Player Value Score": None,
            "Offensive Impact": None,
            "5v5 Driving Impact": None,
            "Defensive Impact": None,
            "Special Teams Impact": None,
        }

    microstats_row = get_microstats_row(player)

    offensive_components = [
        (get_player_percentile(player_data, player, "points_per_60"), 0.40),
        (get_player_percentile(player_data, player, "expected_goals_per_60"), 0.25),
        (get_player_percentile(player_data, player, "shots_per_60"), 0.15),
        (get_player_percentile(player_data, player, "onIce_xGoalsPercentage"), 0.05),
    ]

    play_driving_components = [
        (get_player_percentile(player_data, player, "onIce_xGoalsPercentage"), 0.20),
        (get_player_percentile(player_data, player, "onIce_corsiPercentage"), 0.10),
        (get_player_percentile(player_data, player, "onIce_fenwickPercentage"), 0.10),
    ]

    power_play_score = weighted_average_percentiles(
        [
            (get_player_percentile(player_data, player, "pp_points_per_60"), 0.45),
            (get_player_percentile(player_data, player, "pp_shots"), 0.20),
            (get_player_percentile(player_data, player, "pp_goals"), 0.15),
            (get_player_percentile(player_data, player, "pp_on_ice_xgoals_percentage"), 0.20),
        ]
    )
    penalty_kill_score = weighted_average_percentiles(
        [
            (get_player_percentile(player_data, player, "pk_xgoals_against_per_60", False), 0.35),
            (get_player_percentile(player_data, player, "pk_blocks"), 0.25),
            (get_player_percentile(player_data, player, "pk_takeaways"), 0.20),
            (get_player_percentile(player_data, player, "pk_points"), 0.20),
        ]
    )

    if player["position_group"] == "D":
        defensive_components = [
            (get_player_percentile(player_data, player, "on_ice_xgoals_against_per_60", False), 0.20),
            (get_player_percentile(player_data, player, "onIce_xGoalsPercentage"), 0.15),
            (get_player_percentile(player_data, player, "onIce_fenwickPercentage"), 0.10),
        ]
    elif player["position"] == "C":
        defensive_components = [
            (get_player_percentile(player_data, player, "on_ice_xgoals_against_per_60", False), 0.15),
            (get_player_percentile(player_data, player, "onIce_xGoalsPercentage"), 0.10),
            (get_player_percentile(player_data, player, "onIce_fenwickPercentage"), 0.05),
            (get_player_percentile(player_data, player, "takeaways_per_60"), 0.20),
            (penalty_kill_score, 0.15),
        ]
    else:
        defensive_components = [
            (get_player_percentile(player_data, player, "on_ice_xgoals_against_per_60", False), 0.25),
            (get_player_percentile(player_data, player, "onIce_xGoalsPercentage"), 0.20),
            (get_player_percentile(player_data, player, "onIce_fenwickPercentage"), 0.10),
            (get_player_percentile(player_data, player, "takeaways_per_60"), 0.15),
            (penalty_kill_score, 0.10),
        ]

    special_teams_components = [
        (power_play_score, 0.50),
        (penalty_kill_score, 0.50),
    ]

    if microstats_row is not None:
        offensive_components.extend(
            [
                (get_micro_rate_percentile(microstats_row, "Chances"), 0.05),
                (get_micro_rate_percentile(microstats_row, "Primary Shot Assists"), 0.05),
                (get_micro_rate_percentile(microstats_row, "Chance Assists"), 0.05),
            ]
        )
        play_driving_components.extend(
            [
                (get_micro_rate_percentile(microstats_row, "Zone Entries"), 0.20),
                (get_micro_percentage_percentile(microstats_row, "Carries", "Zone Entries"), 0.20),
                (get_micro_percentage_percentile(microstats_row, "Exits w/ Possession", "Zone Exits"), 0.20),
            ]
        )
        if player["position_group"] == "D":
            defensive_components.extend(
                [
                    (get_micro_rate_percentile(microstats_row, "Denials"), 0.15),
                    (get_micro_rate_percentile(microstats_row, "DZ Retrievals"), 0.15),
                    (
                        get_micro_percentage_percentile(
                            microstats_row,
                            "Retrievals Leading to Exits",
                            "DZ Retrievals",
                        ),
                        0.15,
                    ),
                    (
                        get_micro_percentage_percentile(
                            microstats_row,
                            "Exits w/ Possession",
                            "Zone Exits",
                        ),
                        0.10,
                    ),
                ]
            )
        elif player["position"] == "C":
            defensive_components.extend(
                [
                    (get_micro_rate_percentile(microstats_row, "Forecheck Pressures"), 0.15),
                    (get_micro_rate_percentile(microstats_row, "DZ Retrievals"), 0.10),
                    (get_micro_percentage_percentile(microstats_row, "Exits w/ Possession", "Zone Exits"), 0.10),
                ]
            )
        else:
            defensive_components.extend(
                [
                    (get_micro_rate_percentile(microstats_row, "Forecheck Pressures"), 0.15),
                    (get_micro_percentage_percentile(microstats_row, "Exits w/ Possession", "Zone Exits"), 0.05),
                ]
            )

    total_toi_percentile = get_player_percentile(player_data, player, "total_toi_per_game")
    special_teams_toi_percentile = get_special_teams_toi_percentile(player_data, player)
    special_teams_toi_per_game = get_special_teams_toi_per_game(player)
    has_enough_special_teams_time = special_teams_toi_per_game >= SPECIAL_TEAMS_TOI_MINIMUM

    raw_offensive_impact = weighted_average_percentiles(offensive_components)
    raw_play_driving_impact = weighted_average_percentiles(play_driving_components)
    raw_defensive_impact = weighted_average_percentiles(defensive_components)
    raw_special_teams_impact = None

    if has_enough_special_teams_time:
        raw_special_teams_impact = weighted_average_percentiles(special_teams_components)

    offensive_impact = adjust_score_for_usage(
        raw_offensive_impact,
        total_toi_percentile,
        0.80,
        1.15,
    )
    play_driving_impact = adjust_score_for_usage(
        raw_play_driving_impact,
        total_toi_percentile,
        0.80,
        1.15,
    )
    defensive_impact = adjust_score_for_usage(
        raw_defensive_impact,
        total_toi_percentile,
        0.80,
        1.15,
    )
    defensive_impact = add_defensive_usage_boost(defensive_impact, total_toi_percentile)
    special_teams_impact = None

    if has_enough_special_teams_time:
        special_teams_impact = adjust_score_for_usage(
            raw_special_teams_impact,
            special_teams_toi_percentile,
            0.60,
            1.30,
        )

    if player.get("games_played", 0) < FULL_TRUST_GAMES:
        offensive_impact = shrink_score_toward_average(offensive_impact, SMALL_SAMPLE_TRUST)
        play_driving_impact = shrink_score_toward_average(play_driving_impact, SMALL_SAMPLE_TRUST)
        defensive_impact = shrink_score_toward_average(defensive_impact, SMALL_SAMPLE_TRUST)
        special_teams_impact = shrink_score_toward_average(special_teams_impact, SMALL_SAMPLE_TRUST)

    special_teams_overall_score = special_teams_impact

    if special_teams_overall_score is None:
        special_teams_overall_score = LIMITED_SPECIAL_TEAMS_OVERALL_SCORE

    player_value_score = weighted_average_percentiles(
        [
            (offensive_impact, 0.40),
            (defensive_impact, 0.25),
            (play_driving_impact, 0.20),
            (special_teams_overall_score, 0.15),
        ]
    )

    return {
        "Player Value Score": player_value_score,
        "Offensive Impact": offensive_impact,
        "5v5 Driving Impact": play_driving_impact,
        "Defensive Impact": defensive_impact,
        "Special Teams Impact": special_teams_impact,
    }


def show_impact_card(label, score):
    """
    Show one impact score as a colored card.
    """
    if score is None or pd.isna(score):
        st.metric(label, "NA")
        return

    rounded_score = round(score)
    card_color = get_percentile_color(rounded_score)

    st.markdown(
        f"""
        <div style="
            border: 1px solid rgba(120,120,120,0.25);
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;">
            <div style="font-size: 0.95rem; font-weight: 700; margin-bottom: 8px;">
                {label}
            </div>
            <div style="font-size: 2.2rem; font-weight: 800; color: {card_color}; line-height: 1;">
                {rounded_score}
            </div>
            <div style="font-size: 0.8rem; opacity: 0.75; margin-top: 4px;">
                out of 100
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_impact_scores(player, player_data):
    """
    Show our first simple player value model.
    """
    st.header("Impact Score")
    st.caption(
        "These are WAR-like scores, not true WAR. They combine same-position percentiles from MoneyPuck, special teams, and microstats when available."
    )

    if player.get("games_played", 0) < MINIMUM_GAMES_FOR_IMPACT:
        st.info(
            f"Impact Scores need at least {MINIMUM_GAMES_FOR_IMPACT} games. This player has only {int(player['games_played'])} games, so the scores show as NA."
        )

    impact_scores = calculate_impact_scores(player, player_data)
    score_columns = st.columns(5)

    for score_column, (label, score) in zip(score_columns, impact_scores.items()):
        with score_column:
            show_impact_card(label, score)

    with st.expander("How these scores are built"):
        total_toi_percentile = get_player_percentile(player_data, player, "total_toi_per_game")
        special_teams_toi_percentile = get_special_teams_toi_percentile(player_data, player)
        special_teams_toi_per_game = get_special_teams_toi_per_game(player)

        st.write(
            "Offensive Impact is weighted toward individual production and creation: Points/60, individual expected goals, shots, and offensive microstats. 5v5 On-Ice xG% is now only a small supporting piece."
        )
        st.write(
            "5v5 Driving Impact still uses on-ice xG%, Corsi%, and Fenwick%, but microstats like entries and possession exits now carry more of the grade."
        )
        st.write(
            "Defensive Impact is position-specific. Defensemen get more credit for denials, retrievals, retrievals leading to exits, possession exits, and 5v5 play-driving. Centers get more credit for takeaways, low-zone support, PK value, retrievals, and forecheck pressure. Wingers get more credit for takeaways, forecheck pressure, and shot/chance suppression."
        )
        st.write(
            "Special Teams Impact gives equal room to power-play value and penalty-kill value. It now leans more on individual PP production, PP shot/goals involvement, PK blocks, PK takeaways, and shorthanded points, while team-driven PP xG% and PK xGA/60 are smaller pieces."
        )
        st.write(
            "Player Value Score is weighted as: Offensive Impact 40%, Defensive Impact 25%, 5v5 Driving Impact 20%, and Special Teams Impact 15%."
        )
        st.write(
            "Sample-size rule: players under 10 games show NA. Players from 10-24 games have scores pulled toward 50 with a 65% trust factor. Players at 25+ games get normal scoring."
        )
        st.write(
            "Percentile rule: players under 10 games are also removed from comparison pools, so tiny samples do not distort rankings."
        )
        st.write(
            "TOI adjustment: normal impact scores use a trust range from 80% to 115%. That means low-usage players get pulled toward 50, while high-usage players can move slightly farther from 50."
        )
        st.write(
            "Defensive usage boost: players in the 55th, 70th, and 85th total-TOI percentiles can receive small defensive boosts of +1, +3, and +5."
        )
        st.write(
            "Special teams TOI adjustment: PP/PK ice time is used as a confidence adjustment with a 60% to 130% trust range. It matters more than even-strength TOI because special-teams samples are noisier, but it is not one of the main skill stats."
        )
        st.write(
            f"If a player is below {SPECIAL_TEAMS_TOI_MINIMUM} combined PP+PK minutes per game, Special Teams Impact shows as NA and counts as {LIMITED_SPECIAL_TEAMS_OVERALL_SCORE}/100 in Player Value Score."
        )
        st.write(
            f"This player's combined PP+PK TOI/G is {round(special_teams_toi_per_game, 2)}."
        )
        st.write(
            f"This player's total TOI usage rank is {format_percentile_label(total_toi_percentile)}."
        )
        st.write(
            f"This player's special teams TOI usage rank is {format_percentile_label(special_teams_toi_percentile)}."
        )


def show_tracking_tools(player):
    """
    Show NHL EDGE Player & Puck Tracking stats.
    """
    edge_data = load_nhl_edge_data(get_player_id(player))

    st.subheader("Tracking Tools")
    st.caption(
        "Official NHL EDGE tracking data. These stats measure physical tools and puck-tracking events, not the same things as MoneyPuck impact stats."
    )

    if edge_data is None:
        st.write("Tracking data is not available for this player right now.")
        return

    high_danger_summary = get_shot_location_summary(edge_data, "high")

    skating_speed = get_nested_value(edge_data, ["skatingSpeed", "speedMax"])
    speed_bursts = get_nested_value(edge_data, ["skatingSpeed", "burstsOver20"])
    top_shot_speed = edge_data.get("topShotSpeed", {})
    total_distance = edge_data.get("totalDistanceSkated", {})
    distance_max_game = edge_data.get("distanceMaxGame", {})
    zone_time = edge_data.get("zoneTimeDetails", {})

    first_row = st.columns(4)

    with first_row[0]:
        show_stat(
            "Max Speed",
            f"{format_edge_number(skating_speed.get('imperial') if skating_speed else None)} mph",
        )
        show_quality_indicator(edge_percentile_to_100(skating_speed.get("percentile") if skating_speed else None))

    with first_row[1]:
        show_stat(
            "Speed Bursts 20+ mph",
            format_edge_number(speed_bursts.get("value") if speed_bursts else None, 0),
        )
        show_quality_indicator(edge_percentile_to_100(speed_bursts.get("percentile") if speed_bursts else None))

    with first_row[2]:
        show_stat(
            "Hardest Shot",
            f"{format_edge_number(top_shot_speed.get('imperial'))} mph",
        )
        show_quality_indicator(edge_percentile_to_100(top_shot_speed.get("percentile")))

    with first_row[3]:
        show_stat(
            "Total Distance",
            f"{format_edge_number(total_distance.get('imperial'))} mi",
        )
        show_quality_indicator(edge_percentile_to_100(total_distance.get("percentile")))

    second_row = st.columns(4)

    with second_row[0]:
        show_stat(
            "Most Miles In Game",
            f"{format_edge_number(distance_max_game.get('imperial'))} mi",
        )
        show_quality_indicator(edge_percentile_to_100(distance_max_game.get("percentile")))

    with second_row[1]:
        show_stat(
            "High-Danger Shots",
            format_edge_number(high_danger_summary.get("shots"), 0),
        )
        show_quality_indicator(edge_percentile_to_100(high_danger_summary.get("shotsPercentile")))

    with second_row[2]:
        show_stat(
            "O-Zone Time",
            format_optional_percentage(zone_time.get("offensiveZonePctg")),
        )
        show_quality_indicator(edge_percentile_to_100(zone_time.get("offensiveZonePercentile")))

    with second_row[3]:
        show_stat(
            "5v5 O-Zone Time",
            format_optional_percentage(zone_time.get("offensiveZoneEvPctg")),
        )
        show_quality_indicator(edge_percentile_to_100(zone_time.get("offensiveZoneEvPercentile")))


def show_microstats(player):
    """
    Show All Three Zones microstats when the local data file exists.
    """
    microstats_row = get_microstats_row(player)

    with st.expander("Microstats"):
        show_tracking_tools(player)
        st.divider()
        st.caption(
            "Microstats source: All Three Zones / Corey Sznajder. These stats describe how a player creates offence, enters/exits zones, forechecks, and defends entries at 5v5."
        )

        if microstats_row is None:
            st.write("Microstats are not available for this player.")
            return

        st.subheader("Offensive Creation")
        offense_columns = st.columns(4)

        with offense_columns[0]:
            show_stat("Shots/60", calculate_micro_per_60(microstats_row, "Shots"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Shots"))
        with offense_columns[1]:
            show_stat("Chances/60", calculate_micro_per_60(microstats_row, "Chances"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Chances"))
        with offense_columns[2]:
            show_stat("Primary Shot Assists/60", calculate_micro_per_60(microstats_row, "Primary Shot Assists"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Primary Shot Assists"))
        with offense_columns[3]:
            show_stat("Chance Assists/60", calculate_micro_per_60(microstats_row, "Chance Assists"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Chance Assists"))

        st.subheader("Transition")
        transition_columns = st.columns(4)

        with transition_columns[0]:
            show_stat("Zone Entries/60", calculate_micro_per_60(microstats_row, "Zone Entries"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Zone Entries"))
        with transition_columns[1]:
            show_stat("Controlled Entry%", calculate_micro_percentage(microstats_row, "Carries", "Zone Entries"))
            show_quality_indicator(get_micro_percentage_percentile(microstats_row, "Carries", "Zone Entries"))
        with transition_columns[2]:
            show_stat("Entry Pass Plays/60", calculate_micro_per_60(microstats_row, "Entries w/ Passing Play"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Entries w/ Passing Play"))
        with transition_columns[3]:
            show_stat("Entry Chances/60", calculate_micro_per_60(microstats_row, "Carries w/ Chances"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Carries w/ Chances"))

        st.subheader("Rush, Forecheck, and Exits")
        puck_movement_columns = st.columns(4)

        with puck_movement_columns[0]:
            show_stat("Rush Shots/60", calculate_micro_per_60(microstats_row, "Shots off Rush"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Shots off Rush"))
        with puck_movement_columns[1]:
            show_stat("Forecheck Pressures/60", calculate_micro_per_60(microstats_row, "Forecheck Pressures"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Forecheck Pressures"))
        with puck_movement_columns[2]:
            show_stat("Zone Exits/60", calculate_micro_per_60(microstats_row, "Zone Exits"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Zone Exits"))
        with puck_movement_columns[3]:
            show_stat("Possession Exit%", calculate_micro_percentage(microstats_row, "Exits w/ Possession", "Zone Exits"))
            show_quality_indicator(get_micro_percentage_percentile(microstats_row, "Exits w/ Possession", "Zone Exits"))

        st.subheader("Defense and Breakouts")
        defense_columns = st.columns(4)

        with defense_columns[0]:
            show_stat("DZ Puck Touches/60", calculate_micro_per_60(microstats_row, "DZ Puck Touches"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "DZ Puck Touches"))
        with defense_columns[1]:
            show_stat("DZ Retrievals/60", calculate_micro_per_60(microstats_row, "DZ Retrievals"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "DZ Retrievals"))
        with defense_columns[2]:
            show_stat("Retrievals to Exits%", calculate_micro_percentage(microstats_row, "Retrievals Leading to Exits", "DZ Retrievals"))
            show_quality_indicator(get_micro_percentage_percentile(microstats_row, "Retrievals Leading to Exits", "DZ Retrievals"))
        with defense_columns[3]:
            show_stat("Entry Denials/60", calculate_micro_per_60(microstats_row, "Denials"))
            show_quality_indicator(get_micro_rate_percentile(microstats_row, "Denials"))


def show_power_play_stats_content(player, player_data):
    """
    Show important power-play stats.
    """
    pp_columns = st.columns(3)

    with pp_columns[0]:
        show_stat("PP TOI/G", format_optional_minutes(player.get("pp_toi_per_game", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pp_toi_per_game", player))
        show_stat("PP Goals", format_optional_number(player.get("pp_goals", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pp_goals", player))

    with pp_columns[1]:
        show_stat("PP Points", format_optional_number(player.get("pp_points", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pp_points", player))
        show_stat("PP Points/60", format_optional_number(player.get("pp_points_per_60", pd.NA), 2))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pp_points_per_60", player))

    with pp_columns[2]:
        show_stat("PP Shots", format_optional_number(player.get("pp_shots", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pp_shots", player))
        show_stat(
            "PP On-Ice xG%",
            format_optional_percentage(
                player.get("pp_on_ice_xgoals_percentage", pd.NA)
            ),
        )
        show_quality_indicator(calculate_player_data_percentile(player_data, "pp_on_ice_xgoals_percentage", player))


def show_penalty_kill_stats_content(player, player_data):
    """
    Show important penalty-kill stats.

    PK offense is limited to shorthanded goals and points.
    """
    pk_columns = st.columns(3)

    with pk_columns[0]:
        show_stat("PK TOI/G", format_optional_minutes(player.get("pk_toi_per_game", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pk_toi_per_game", player))
        show_stat("SH Goals", format_optional_number(player.get("pk_goals", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pk_goals", player))

    with pk_columns[1]:
        show_stat("SH Points", format_optional_number(player.get("pk_points", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pk_points", player))
        show_stat("PK Blocks", format_optional_number(player.get("pk_blocks", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pk_blocks", player))

    with pk_columns[2]:
        show_stat("PK Takeaways", format_optional_number(player.get("pk_takeaways", pd.NA)))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pk_takeaways", player))
        show_stat("PK xGA/60", format_optional_number(player.get("pk_xgoals_against_per_60", pd.NA), 2))
        show_quality_indicator(calculate_player_data_percentile(player_data, "pk_xgoals_against_per_60", player, higher_is_better=False))


def show_special_teams_stats(player, player_data):
    """
    Show power-play and penalty-kill stats in one section.
    """
    with st.expander("Special Teams"):
        power_play_tab, penalty_kill_tab = st.tabs(["Power Play", "Penalty Kill"])

        with power_play_tab:
            show_power_play_stats_content(player, player_data)

        with penalty_kill_tab:
            show_penalty_kill_stats_content(player, player_data)


def show_rate_stats(player, player_data):
    """
    Show per-game and per-60 stats.
    """
    with st.expander("Rate Stats"):
        per_game_tab, per_60_tab = st.tabs(["Per Game", "Per 60"])

        with per_game_tab:
            stat_columns = st.columns(4)

            with stat_columns[0]:
                show_stat("Goals/Game", player["goals_per_game"])
                show_quality_indicator(calculate_player_data_percentile(player_data, "goals_per_game", player))
            with stat_columns[1]:
                show_stat("Points/Game", player["points_per_game"])
                show_quality_indicator(player["points_per_game_percentile"])
            with stat_columns[2]:
                show_stat("Shots/Game", player["shots_per_game"])
                show_quality_indicator(calculate_player_data_percentile(player_data, "shots_per_game", player))
            with stat_columns[3]:
                show_stat("xGoals/Game", player["expected_goals_per_game"])
                show_quality_indicator(calculate_player_data_percentile(player_data, "expected_goals_per_game", player))

        with per_60_tab:
            stat_columns = st.columns(4)

            with stat_columns[0]:
                show_stat("Goals/60", player["goals_per_60"])
                show_quality_indicator(player["goals_per_60_percentile"])
            with stat_columns[1]:
                show_stat("Points/60", player["points_per_60"])
                show_quality_indicator(player["points_per_60_percentile"])
            with stat_columns[2]:
                show_stat("Shots/60", player["shots_per_60"])
                show_quality_indicator(player["shots_per_60_percentile"])
            with stat_columns[3]:
                show_stat("xGoals/60", player["expected_goals_per_60"])
                show_quality_indicator(player["expected_goals_per_60_percentile"])


def build_single_player_comparison_chart(comparison_table, player_name, percentile_column, value_column):
    """
    Build one player's comparison chart.

    Each chart uses the same stat list, so the left and right sides are easy to compare.
    """
    bar_colors = [
        get_percentile_color(value) if not pd.isna(value) else "#8a8f98"
        for value in comparison_table[percentile_column]
    ]

    player_chart = go.Figure()
    player_chart.add_trace(
        go.Bar(
            y=comparison_table["Stat"],
            x=comparison_table[percentile_column],
            orientation="h",
            marker_color=bar_colors,
            text=comparison_table[value_column],
            textposition="outside",
            hovertemplate=(
                f"{player_name}<br>"
                "%{y}<br>"
                "Percentile: %{x:.0f}<br>"
                "Value: %{text}<extra></extra>"
            ),
        )
    )
    player_chart.update_layout(
        height=560,
        margin={"l": 10, "r": 20, "t": 10, "b": 20},
        xaxis_title="Same-position percentile",
        xaxis_range=[0, 105],
        yaxis_autorange="reversed",
        showlegend=False,
    )

    return player_chart


def format_score_for_card(score):
    """
    Format an impact score for a compact player card.
    """
    if score is None or pd.isna(score):
        return "NA"

    return str(round(score))


def show_comparison_player_card(player, player_data):
    """
    Show a compact player card for the comparison page.
    """
    impact_scores = calculate_impact_scores(player, player_data)
    position = format_position(player["position"])
    season_range = format_season_range(player["season"])
    team_logo_url = get_team_logo_url(player["team"])
    headshot_image = load_headshot_or_blank(player)

    header_columns = st.columns([1, 1, 3])

    with header_columns[0]:
        st.image(headshot_image, width=90)

    with header_columns[1]:
        st.image(team_logo_url, width=80)

    with header_columns[2]:
        st.subheader(player["name"])
        st.caption(f"{player['team']} | {position} | {season_range}")

    if player.get("games_played", 0) < MINIMUM_GAMES_FOR_IMPACT:
        st.info(f"Small sample: {int(player['games_played'])} games")

    score_columns = st.columns(2)

    with score_columns[0]:
        show_stat("Player Value", format_score_for_card(impact_scores["Player Value Score"]))
        show_stat("Offense", format_score_for_card(impact_scores["Offensive Impact"]))
        show_stat("Defense", format_score_for_card(impact_scores["Defensive Impact"]))

    with score_columns[1]:
        show_stat("5v5 Driving", format_score_for_card(impact_scores["5v5 Driving Impact"]))
        show_stat("Special Teams", format_score_for_card(impact_scores["Special Teams Impact"]))
        show_stat("TOI/G", format_optional_minutes(player.get("total_toi_per_game", pd.NA)))

    stat_columns = st.columns(4)

    with stat_columns[0]:
        show_stat("Goals", format_optional_number(player.get("total_goals", player["I_F_goals"])))
    with stat_columns[1]:
        show_stat("Points", format_optional_number(player.get("total_points", player["I_F_points"])))
    with stat_columns[2]:
        show_stat("Shots", format_optional_number(player.get("total_shots", player["I_F_shotsOnGoal"])))
    with stat_columns[3]:
        show_stat("5v5 xG%", format_optional_percentage(player.get("onIce_xGoalsPercentage", pd.NA)))

    st.write(generate_scouting_report(player, player_data))


def build_impact_comparison_chart(first_player, second_player, player_data):
    """
    Build a chart that compares the main impact scores for two players.
    """
    first_scores = calculate_impact_scores(first_player, player_data)
    second_scores = calculate_impact_scores(second_player, player_data)
    impact_labels = [
        "Player Value",
        "Offense",
        "Defense",
        "5v5 Driving",
        "Special Teams",
    ]
    score_keys = [
        "Player Value Score",
        "Offensive Impact",
        "Defensive Impact",
        "5v5 Driving Impact",
        "Special Teams Impact",
    ]
    first_values = [first_scores[key] for key in score_keys]
    second_values = [second_scores[key] for key in score_keys]

    comparison_chart = go.Figure()
    comparison_chart.add_trace(
        go.Bar(
            name=first_player["name"],
            x=impact_labels,
            y=first_values,
            marker_color=[
                get_percentile_color(value) if value is not None and not pd.isna(value) else "#8a8f98"
                for value in first_values
            ],
            text=[format_score_for_card(value) for value in first_values],
            textposition="outside",
            hovertemplate="%{x}<br>Score: %{text}<extra></extra>",
        )
    )
    comparison_chart.add_trace(
        go.Bar(
            name=second_player["name"],
            x=impact_labels,
            y=second_values,
            marker={
                "color": [
                    get_percentile_color(value) if value is not None and not pd.isna(value) else "#8a8f98"
                    for value in second_values
                ],
                "pattern": {"shape": "/", "fgcolor": "rgba(255,255,255,0.8)", "size": 8},
            },
            text=[format_score_for_card(value) for value in second_values],
            textposition="outside",
            hovertemplate="%{x}<br>Score: %{text}<extra></extra>",
        )
    )
    comparison_chart.update_layout(
        barmode="group",
        height=430,
        yaxis_title="Impact Score",
        yaxis_range=[0, 105],
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        legend_orientation="h",
    )

    return comparison_chart


def build_comparison_rows(player_data, first_player, second_player):
    """
    Build the broad detailed comparison table.
    """
    first_scores = calculate_impact_scores(first_player, player_data)
    second_scores = calculate_impact_scores(second_player, player_data)

    comparison_rows = []

    impact_stats = [
        "Player Value Score",
        "Offensive Impact",
        "Defensive Impact",
        "5v5 Driving Impact",
        "Special Teams Impact",
    ]

    for stat_name in impact_stats:
        comparison_rows.append(
            {
                "Stat": stat_name,
                "Player 1 Value": format_score_for_card(first_scores[stat_name]),
                "Player 1 Percentile": first_scores[stat_name],
                "Player 2 Value": format_score_for_card(second_scores[stat_name]),
                "Player 2 Percentile": second_scores[stat_name],
            }
        )

    comparison_stats = [
        ("Games", "games_played", "number", True),
        ("TOI/G", "total_toi_per_game", "number", True),
        ("Goals", "total_goals", "number", True),
        ("Points", "total_points", "number", True),
        ("Shots", "total_shots", "number", True),
        ("Hits", "total_hits", "number", True),
        ("Blocks", "total_blocks", "number", True),
        ("Takeaways", "total_takeaways", "number", True),
        ("Goals/Game", "goals_per_game", "number", True),
        ("Points/60", "points_per_60", "number", True),
        ("Shots/60", "shots_per_60", "number", True),
        ("Individual xG/60", "expected_goals_per_60", "number", True),
        ("5v5 On-Ice xG%", "onIce_xGoalsPercentage", "percentage", True),
        ("5v5 On-Ice xGF/60", "on_ice_xgoals_for_per_60", "number", True),
        ("5v5 On-Ice xGA/60", "on_ice_xgoals_against_per_60", "number", False),
        ("5v5 Corsi%", "onIce_corsiPercentage", "percentage", True),
        ("5v5 Fenwick%", "onIce_fenwickPercentage", "percentage", True),
        ("PP TOI/G", "pp_toi_per_game", "number", True),
        ("PP Points", "pp_points", "number", True),
        ("PP Points/60", "pp_points_per_60", "number", True),
        ("PP On-Ice xG%", "pp_on_ice_xgoals_percentage", "percentage", True),
        ("PK TOI/G", "pk_toi_per_game", "number", True),
        ("SH Points", "pk_points", "number", True),
        ("PK xGA/60", "pk_xgoals_against_per_60", "number", False),
        ("PK Blocks", "pk_blocks", "number", True),
        ("PK Takeaways", "pk_takeaways", "number", True),
    ]

    for stat_name, column_name, value_type, higher_is_better in comparison_stats:
        first_value = first_player.get(column_name, pd.NA)
        second_value = second_player.get(column_name, pd.NA)
        first_percentile = calculate_player_data_percentile(
            player_data,
            column_name,
            first_player,
            higher_is_better,
        )
        second_percentile = calculate_player_data_percentile(
            player_data,
            column_name,
            second_player,
            higher_is_better,
        )

        comparison_rows.append(
            {
                "Stat": stat_name,
                "Player 1 Value": format_comparison_value(first_value, value_type),
                "Player 1 Percentile": first_percentile,
                "Player 2 Value": format_comparison_value(second_value, value_type),
                "Player 2 Percentile": second_percentile,
            }
        )

    return comparison_rows


def show_player_comparison(player_data, selected_player):
    """
    Let the user compare two players side by side.

    Most comparison stats are rates so players with different ice time
    can still be compared fairly.
    """
    st.header("Compare Players")
    st.caption(
        "Bars show same-position percentiles, so defensemen are compared to defensemen and forwards to forwards."
    )

    seasons = sorted(player_data["season"].unique())
    season_labels = {format_season_range(season): season for season in seasons}
    selected_player_season_label = format_season_range(selected_player["season"])
    selected_season_index = list(season_labels.keys()).index(selected_player_season_label)

    season_column, first_player_column, second_player_column = st.columns(3)

    with season_column:
        selected_season_label = st.selectbox(
            "Choose comparison season",
            list(season_labels.keys()),
            index=selected_season_index,
            key="comparison_season",
        )

    selected_season = season_labels[selected_season_label]
    season_data = player_data[player_data["season"] == selected_season].copy()
    season_data["player_label"] = season_data.apply(get_player_label, axis=1)
    season_data = season_data.sort_values("player_label")

    player_labels = season_data["player_label"].tolist()
    selected_player_label = get_player_label(selected_player)
    first_player_index = 0

    if selected_player_label in player_labels:
        first_player_index = player_labels.index(selected_player_label)

    second_player_index = 1 if len(player_labels) > 1 else 0

    if second_player_index == first_player_index and len(player_labels) > 1:
        second_player_index = 0

    with first_player_column:
        first_player_label = st.selectbox(
            "First player",
            player_labels,
            index=first_player_index,
            key=f"first_comparison_player_{get_player_id(selected_player)}_{selected_season}",
        )

    with second_player_column:
        second_player_label = st.selectbox(
            "Second player",
            player_labels,
            index=second_player_index,
            key=f"second_comparison_player_{selected_season}",
        )

    first_player = season_data[season_data["player_label"] == first_player_label].iloc[0]
    second_player = season_data[season_data["player_label"] == second_player_label].iloc[0]

    first_player_name = first_player["name"]
    second_player_name = second_player["name"]
    comparison_rows = build_comparison_rows(season_data, first_player, second_player)

    st.caption("Impact Score graph is shown first. The detailed stat table is below.")
    st.caption("Color shows score quality. Solid bars are the first player, striped bars are the second player.")

    impact_chart = build_impact_comparison_chart(first_player, second_player, season_data)
    st.plotly_chart(impact_chart, use_container_width=True)

    st.divider()
    st.subheader("Detailed Comparison Table")
    st.caption("Lower is better for 5v5 On-Ice xGA/60 and PK xGA/60. Higher is better for the other stats.")

    first_value_column = f"{first_player_name} Value"
    first_rank_column = f"{first_player_name} Rank"
    second_value_column = f"{second_player_name} Value"
    second_rank_column = f"{second_player_name} Rank"

    if first_player_name == second_player_name:
        first_value_column = f"{first_player_name} Value 1"
        first_rank_column = f"{first_player_name} Rank 1"
        second_value_column = f"{second_player_name} Value 2"
        second_rank_column = f"{second_player_name} Rank 2"

    table_rows = []

    for row in comparison_rows:
        table_rows.append(
            {
                "Stat": row["Stat"],
                first_value_column: row["Player 1 Value"],
                first_rank_column: format_percentile_label(row["Player 1 Percentile"]),
                second_value_column: row["Player 2 Value"],
                second_rank_column: format_percentile_label(row["Player 2 Percentile"]),
            }
        )

    st.dataframe(
        pd.DataFrame(table_rows),
        hide_index=True,
        use_container_width=True,
    )


def show_percentiles(player, player_data):
    """
    Show the most important percentile rankings.
    """
    st.header("5v5 Percentile Rankings")
    impact_scores = calculate_impact_scores(player, player_data)
    player_value_score = impact_scores["Player Value Score"]

    percentile_columns = st.columns(2)

    with percentile_columns[0]:
        if player_value_score is not None and not pd.isna(player_value_score):
            show_percentile("Player Value Score", player_value_score)
        show_percentile("Points/60", player["points_per_60_percentile"])
        show_percentile("Expected Goals/60", player["expected_goals_per_60_percentile"])

    with percentile_columns[1]:
        show_percentile("5v5 On-Ice xGoals %", player["onIce_xGoalsPercentage_percentile"])
        show_percentile("5v5 Corsi %", player["onIce_corsiPercentage_percentile"])
        show_percentile("5v5 Fenwick %", player["onIce_fenwickPercentage_percentile"])


def describe_impact_score(score):
    """
    Convert a numeric impact score into plain hockey language.
    """
    if score is None or pd.isna(score):
        return "not enough sample"

    if score >= 85:
        return "elite"

    if score >= 70:
        return "strong"

    if score >= 55:
        return "solid"

    if score >= 45:
        return "average"

    if score >= 35:
        return "below average"

    return "poor"


def classify_player_role(player, impact_scores):
    """
    Choose a simple role label from the new impact scores.
    """
    offense = impact_scores["Offensive Impact"]
    defense = impact_scores["Defensive Impact"]
    player_value = impact_scores["Player Value Score"]

    if player["position_group"] == "D":
        if player_value is not None and player_value >= 75:
            return "top-pair defenseman"

        if player_value is not None and player_value >= 60:
            return "top-four defenseman"

        if offense is not None and offense >= 70:
            return "offensive defenseman"

        if defense is not None and defense >= 70:
            return "defensive defenseman"

        return "depth defenseman"

    if player_value is not None and player_value >= 80:
        return "first-line forward"

    if offense is not None and offense >= 65 and defense is not None and defense >= 70:
        return "two-way top-six forward"

    if offense is not None and offense >= 70:
        return "top-six offensive forward"

    if defense is not None and defense >= 70:
        return "defensive specialist"

    if player_value is not None and player_value >= 55:
        return "middle-six forward"

    return "depth forward"


def generate_scouting_report(player, player_data):
    """
    Generate a concise scouting report using the newest impact scores.
    """
    games_played = int(player["games_played"])

    if games_played < MINIMUM_GAMES_FOR_IMPACT:
        return (
            f"{player['name']} has only played {games_played} games, so the sample is too small for a reliable scouting read. "
            "The app shows Impact Scores as NA because tiny samples can create misleading ratings. "
            "Once he reaches the minimum sample, the report will use offense, defense, 5v5 driving, and special-teams impact."
        )

    impact_scores = calculate_impact_scores(player, player_data)
    offense = impact_scores["Offensive Impact"]
    defense = impact_scores["Defensive Impact"]
    driving = impact_scores["5v5 Driving Impact"]
    special_teams = impact_scores["Special Teams Impact"]
    player_value = impact_scores["Player Value Score"]
    role = classify_player_role(player, impact_scores)

    offense_level = describe_impact_score(offense)
    defense_level = describe_impact_score(defense)
    driving_level = describe_impact_score(driving)
    special_teams_level = describe_impact_score(special_teams)

    if offense is not None and offense >= 70:
        offensive_sentence = f"Offensively, {player['name']} profiles as a {offense_level} contributor, with his production and chance-impact indicators driving the grade."
    elif offense is not None and offense < 45:
        offensive_sentence = f"Offensively, {player['name']} has a limited profile in this sample and does not show strong production or chance-creation impact."
    else:
        offensive_sentence = f"Offensively, {player['name']} grades as a {offense_level} contributor rather than a clear driver."

    if driving is not None and driving >= 70:
        driving_sentence = "At 5-on-5, his team tends to tilt play positively in his minutes, especially by controlling chance quality."
    elif driving is not None and driving < 45:
        driving_sentence = "At 5-on-5, the play-driving results are a concern and suggest his minutes have not consistently moved play in the right direction."
    else:
        driving_sentence = f"At 5-on-5, his play-driving profile is {driving_level}, with neither dominant nor severely damaging results."

    if defense is not None and defense >= 70:
        defensive_sentence = "Defensively, the model views him as a strong option, with the position-adjusted formula giving credit for suppression, usage, and defensive microstats where available."
    elif defense is not None and defense < 45:
        defensive_sentence = "Defensively, his profile is still a weak point, though this version tries not to over-punish team-driven xGA results."
    else:
        defensive_sentence = f"Defensively, he grades as {defense_level}, so the results are closer to playable than standout."

    if special_teams is None:
        special_teams_sentence = "Special teams value is marked NA because he has not played enough combined PP and PK minutes to grade it fairly."
    else:
        special_teams_sentence = f"His special-teams profile grades as {special_teams_level}, with PP and PK impact separated from the main even-strength read."

    role_sentence = f"Overall, his Player Value Score fits best as a {role}."

    return " ".join(
        [
            offensive_sentence,
            driving_sentence,
            defensive_sentence,
            special_teams_sentence,
            role_sentence,
        ]
    )


def show_strengths_and_weaknesses(player):
    """
    Show the plain-English player notes from Milestone 7.
    """
    st.header("Strengths and Weaknesses")

    note_columns = st.columns(2)

    with note_columns[0]:
        st.subheader("Strengths")
        st.write(player["strengths"])

    with note_columns[1]:
        st.subheader("Weaknesses")
        st.write(player["weaknesses"])


def show_scouting_report(player, player_data):
    """
    Show the generated scouting report.
    """
    st.header("Scouting Report")

    scouting_report = generate_scouting_report(player, player_data)

    st.write(scouting_report)


def main():
    """
    Run the Streamlit app.
    """
    st.set_page_config(
        page_title="Hockey Card Generator",
        page_icon="H",
        layout="wide",
    )

    st.sidebar.title("Hockey Card Generator")
    st.sidebar.write("Choose a player to generate a simple Version 1 card.")

    add_custom_styles()

    player_data = load_player_data()
    selected_player = get_selected_player(player_data)

    player_card_tab, comparison_tab = st.tabs(["Player Card", "Compare Players"])

    with player_card_tab:
        show_player_header(selected_player)
        show_basic_stats(selected_player)
        show_impact_scores(selected_player, player_data)
        show_percentiles(selected_player, player_data)
        show_microstats(selected_player)
        show_special_teams_stats(selected_player, player_data)
        show_rate_stats(selected_player, player_data)
        show_scouting_report(selected_player, player_data)

    with comparison_tab:
        show_player_comparison(player_data, selected_player)


if __name__ == "__main__":
    main()
