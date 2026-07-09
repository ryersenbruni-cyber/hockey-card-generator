import importlib
from pathlib import Path
import re

import pandas as pd
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


def show_nhl_edge_tracking(player):
    """
    Show NHL EDGE Player & Puck Tracking stats.
    """
    edge_data = load_nhl_edge_data(get_player_id(player))

    with st.expander("NHL EDGE Tracking"):
        st.caption(
            "Official NHL EDGE tracking data. These stats measure physical tools and puck-tracking events, not the same things as MoneyPuck impact stats."
        )

        if edge_data is None:
            st.write("NHL EDGE data is not available for this player right now.")
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
            st.caption(f"{format_edge_percentile(skating_speed.get('percentile') if skating_speed else None)} percentile")

        with first_row[1]:
            show_stat(
                "Speed Bursts 20+ mph",
                format_edge_number(speed_bursts.get("value") if speed_bursts else None, 0),
            )
            st.caption(f"{format_edge_percentile(speed_bursts.get('percentile') if speed_bursts else None)} percentile")

        with first_row[2]:
            show_stat(
                "Hardest Shot",
                f"{format_edge_number(top_shot_speed.get('imperial'))} mph",
            )
            st.caption(f"{format_edge_percentile(top_shot_speed.get('percentile'))} percentile")

        with first_row[3]:
            show_stat(
                "Total Distance",
                f"{format_edge_number(total_distance.get('imperial'))} mi",
            )
            st.caption(f"{format_edge_percentile(total_distance.get('percentile'))} percentile")

        second_row = st.columns(4)

        with second_row[0]:
            show_stat(
                "Most Miles In Game",
                f"{format_edge_number(distance_max_game.get('imperial'))} mi",
            )
            st.caption(f"{format_edge_percentile(distance_max_game.get('percentile'))} percentile")

        with second_row[1]:
            show_stat(
                "High-Danger Shots",
                format_edge_number(high_danger_summary.get("shots"), 0),
            )
            st.caption(f"{format_edge_percentile(high_danger_summary.get('shotsPercentile'))} percentile")

        with second_row[2]:
            show_stat(
                "O-Zone Time",
                format_optional_percentage(zone_time.get("offensiveZonePctg")),
            )
            st.caption(f"{format_edge_percentile(zone_time.get('offensiveZonePercentile'))} percentile")

        with second_row[3]:
            show_stat(
                "5v5 O-Zone Time",
                format_optional_percentage(zone_time.get("offensiveZoneEvPctg")),
            )
            st.caption(f"{format_edge_percentile(zone_time.get('offensiveZoneEvPercentile'))} percentile")


def show_microstats(player):
    """
    Show All Three Zones microstats when the local data file exists.
    """
    microstats_row = get_microstats_row(player)

    with st.expander("Microstats"):
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
        with offense_columns[1]:
            show_stat("Chances/60", calculate_micro_per_60(microstats_row, "Chances"))
        with offense_columns[2]:
            show_stat("Primary Shot Assists/60", calculate_micro_per_60(microstats_row, "Primary Shot Assists"))
        with offense_columns[3]:
            show_stat("Chance Assists/60", calculate_micro_per_60(microstats_row, "Chance Assists"))

        st.subheader("Transition")
        transition_columns = st.columns(4)

        with transition_columns[0]:
            show_stat("Zone Entries/60", calculate_micro_per_60(microstats_row, "Zone Entries"))
        with transition_columns[1]:
            show_stat("Controlled Entry%", calculate_micro_percentage(microstats_row, "Carries", "Zone Entries"))
        with transition_columns[2]:
            show_stat("Entry Pass Plays/60", calculate_micro_per_60(microstats_row, "Entries w/ Passing Play"))
        with transition_columns[3]:
            show_stat("Entry Chances/60", calculate_micro_per_60(microstats_row, "Carries w/ Chances"))

        st.subheader("Rush, Forecheck, and Exits")
        puck_movement_columns = st.columns(4)

        with puck_movement_columns[0]:
            show_stat("Rush Shots/60", calculate_micro_per_60(microstats_row, "Shots off Rush"))
        with puck_movement_columns[1]:
            show_stat("Forecheck Pressures/60", calculate_micro_per_60(microstats_row, "Forecheck Pressures"))
        with puck_movement_columns[2]:
            show_stat("Zone Exits/60", calculate_micro_per_60(microstats_row, "Zone Exits"))
        with puck_movement_columns[3]:
            show_stat("Possession Exit%", calculate_micro_percentage(microstats_row, "Exits w/ Possession", "Zone Exits"))

        st.subheader("Defense and Breakouts")
        defense_columns = st.columns(4)

        with defense_columns[0]:
            show_stat("DZ Puck Touches/60", calculate_micro_per_60(microstats_row, "DZ Puck Touches"))
        with defense_columns[1]:
            show_stat("DZ Retrievals/60", calculate_micro_per_60(microstats_row, "DZ Retrievals"))
        with defense_columns[2]:
            show_stat("Retrievals to Exits%", calculate_micro_percentage(microstats_row, "Retrievals Leading to Exits", "DZ Retrievals"))
        with defense_columns[3]:
            show_stat("Entry Denials/60", calculate_micro_per_60(microstats_row, "Denials"))


def show_power_play_stats(player):
    """
    Show important power-play stats.
    """
    with st.expander("Power Play Stats"):
        pp_columns = st.columns(3)

        with pp_columns[0]:
            show_stat("PP TOI/G", format_optional_minutes(player.get("pp_toi_per_game", pd.NA)))
            show_stat("PP Goals", format_optional_number(player.get("pp_goals", pd.NA)))

        with pp_columns[1]:
            show_stat("PP Points", format_optional_number(player.get("pp_points", pd.NA)))
            show_stat("PP Points/60", format_optional_number(player.get("pp_points_per_60", pd.NA), 2))

        with pp_columns[2]:
            show_stat("PP Shots", format_optional_number(player.get("pp_shots", pd.NA)))
            show_stat(
                "PP On-Ice xG%",
                format_optional_percentage(
                    player.get("pp_on_ice_xgoals_percentage", pd.NA)
                ),
            )


def show_penalty_kill_stats(player):
    """
    Show important penalty-kill stats.

    PK offense is limited to shorthanded goals and points.
    """
    with st.expander("Penalty Kill Stats"):
        pk_columns = st.columns(3)

        with pk_columns[0]:
            show_stat("PK TOI/G", format_optional_minutes(player.get("pk_toi_per_game", pd.NA)))
            show_stat("SH Goals", format_optional_number(player.get("pk_goals", pd.NA)))

        with pk_columns[1]:
            show_stat("SH Points", format_optional_number(player.get("pk_points", pd.NA)))
            show_stat("PK Blocks", format_optional_number(player.get("pk_blocks", pd.NA)))

        with pk_columns[2]:
            show_stat("PK Takeaways", format_optional_number(player.get("pk_takeaways", pd.NA)))
            show_stat("PK xGA/60", format_optional_number(player.get("pk_xgoals_against_per_60", pd.NA), 2))


def show_rate_stats(player):
    """
    Show per-game and per-60 stats.
    """
    with st.expander("Rate Stats"):
        per_game_tab, per_60_tab = st.tabs(["Per Game", "Per 60"])

        with per_game_tab:
            stat_columns = st.columns(4)

            with stat_columns[0]:
                show_stat("Goals/Game", player["goals_per_game"])
            with stat_columns[1]:
                show_stat("Points/Game", player["points_per_game"])
            with stat_columns[2]:
                show_stat("Shots/Game", player["shots_per_game"])
            with stat_columns[3]:
                show_stat("xGoals/Game", player["expected_goals_per_game"])

        with per_60_tab:
            stat_columns = st.columns(4)

            with stat_columns[0]:
                show_stat("Goals/60", player["goals_per_60"])
            with stat_columns[1]:
                show_stat("Points/60", player["points_per_60"])
            with stat_columns[2]:
                show_stat("Shots/60", player["shots_per_60"])
            with stat_columns[3]:
                show_stat("xGoals/60", player["expected_goals_per_60"])


def show_player_comparison(player_data, selected_player):
    """
    Let the user compare two players side by side.

    Most comparison stats are rates so players with different ice time
    can still be compared fairly.
    """
    with st.expander("Compare two players"):
        seasons = sorted(player_data["season"].unique())
        season_labels = {format_season_range(season): season for season in seasons}
        selected_player_season_label = format_season_range(selected_player["season"])
        selected_season_index = list(season_labels.keys()).index(selected_player_season_label)
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

        first_player_label = st.selectbox(
            "Choose first comparison player",
            player_labels,
            index=first_player_index,
            key=f"first_comparison_player_{get_player_id(selected_player)}",
        )
        second_player_label = st.selectbox(
            "Choose second comparison player",
            player_labels,
            index=1 if len(player_labels) > 1 else 0,
            key="second_comparison_player",
        )

        first_player = season_data[season_data["player_label"] == first_player_label].iloc[0]
        second_player = season_data[season_data["player_label"] == second_player_label].iloc[0]

        comparison_stats = [
            ("Goals/Game", "goals_per_game", "number"),
            ("Points/Game", "points_per_game", "number"),
            ("Shots/60", "shots_per_60", "number"),
            ("Individual xG/60", "expected_goals_per_60", "number"),
            ("5v5 On-Ice xG%", "onIce_xGoalsPercentage", "percentage"),
            ("5v5 On-Ice xGF/60", "on_ice_xgoals_for_per_60", "number"),
            ("5v5 On-Ice xGA/60", "on_ice_xgoals_against_per_60", "number"),
            ("5v5 Corsi%", "onIce_corsiPercentage", "percentage"),
            ("5v5 Fenwick%", "onIce_fenwickPercentage", "percentage"),
            ("Hits/60", "hits_per_60", "number"),
            ("Blocks/60", "blocks_per_60", "number"),
        ]

        comparison_rows = []

        for stat_name, column_name, value_type in comparison_stats:
            first_value = first_player[column_name]
            second_value = second_player[column_name]

            comparison_rows.append(
                {
                    "Stat": stat_name,
                    first_player["name"]: format_comparison_value(
                        first_value,
                        value_type,
                    ),
                    second_player["name"]: format_comparison_value(
                        second_value,
                        value_type,
                    ),
                }
            )

        comparison_table = pd.DataFrame(comparison_rows)

        st.caption("Most stats are better when higher. For 5v5 On-Ice xGA/60, lower is better.")

        st.dataframe(
            comparison_table,
            column_config={
                "Stat": st.column_config.TextColumn("Stat", width="medium"),
                first_player["name"]: st.column_config.TextColumn(first_player["name"], width="small"),
                second_player["name"]: st.column_config.TextColumn(second_player["name"], width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )


def show_percentiles(player):
    """
    Show the most important percentile rankings.
    """
    st.header("5v5 Percentile Rankings")

    percentile_columns = st.columns(2)

    with percentile_columns[0]:
        show_percentile("Points/Game", player["points_per_game_percentile"])
        show_percentile("Points/60", player["points_per_60_percentile"])
        show_percentile("Expected Goals/60", player["expected_goals_per_60_percentile"])

    with percentile_columns[1]:
        show_percentile("5v5 On-Ice xGoals %", player["onIce_xGoalsPercentage_percentile"])
        show_percentile("5v5 Corsi %", player["onIce_corsiPercentage_percentile"])
        show_percentile("5v5 Fenwick %", player["onIce_fenwickPercentage_percentile"])


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


def show_scouting_report(player):
    """
    Show the generated scouting report.
    """
    st.header("Scouting Report")

    scouting_report = scouting_report_helpers.generate_scouting_report(player)

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
    show_player_comparison(player_data, selected_player)

    show_player_header(selected_player)
    show_basic_stats(selected_player)
    show_nhl_edge_tracking(selected_player)
    show_microstats(selected_player)
    show_power_play_stats(selected_player)
    show_penalty_kill_stats(selected_player)
    show_percentiles(selected_player)
    show_rate_stats(selected_player)
    show_scouting_report(selected_player)


if __name__ == "__main__":
    main()
