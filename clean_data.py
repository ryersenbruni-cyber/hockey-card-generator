import pandas as pd

from utils.calculations import add_per_60_stats, add_per_game_stats, add_toi_per_game_stats
from utils.percentiles import PERCENTILE_STATS, add_percentile_stats
from utils.strengths import add_strengths_and_weaknesses


# This is the path to the raw MoneyPuck skater dataset.
# We keep raw data inside the data folder.
DATA_FILE_PATH = "data/skaters.csv"

# This is where we will save the cleaned dataset.
# The cleaned file is separate from the raw file.
CLEANED_DATA_FILE_PATH = "cleaned_data/skaters_clean.csv"

# This is where we will save the dataset with per-game stats.
PER_GAME_DATA_FILE_PATH = "cleaned_data/skaters_per_game.csv"

# This is where we will save the dataset with per-game and per-60 stats.
PER_60_DATA_FILE_PATH = "cleaned_data/skaters_per_60.csv"

# This is where we will save the dataset with percentile rankings.
PERCENTILE_DATA_FILE_PATH = "cleaned_data/skaters_percentiles.csv"

# This is where we will save the dataset with strengths and weaknesses.
STRENGTHS_DATA_FILE_PATH = "cleaned_data/skaters_strengths.csv"

# These are the columns we want in Version 1.
# We are choosing readable, useful columns for a first player card.
COLUMNS_TO_KEEP = [
    "playerId",
    "season",
    "name",
    "team",
    "position",
    "situation",
    "games_played",
    "icetime",
    "shifts",
    "gameScore",
    "I_F_goals",
    "I_F_primaryAssists",
    "I_F_secondaryAssists",
    "I_F_points",
    "I_F_shotsOnGoal",
    "I_F_xGoals",
    "I_F_hits",
    "I_F_takeaways",
    "I_F_giveaways",
    "penalties",
    "penaltiesDrawn",
    "shotsBlockedByPlayer",
    "OnIce_F_xGoals",
    "OnIce_A_xGoals",
    "onIce_xGoalsPercentage",
    "onIce_corsiPercentage",
    "onIce_fenwickPercentage",
]

# These are full-season counting stats from the "all" situation.
# We keep them separate from the 5-on-5 stats so percentiles can stay even-strength.
TOTAL_STATS_TO_KEEP = [
    "playerId",
    "season",
    "team",
    "icetime",
    "I_F_goals",
    "I_F_primaryAssists",
    "I_F_secondaryAssists",
    "I_F_points",
    "I_F_shotsOnGoal",
    "I_F_hits",
    "I_F_takeaways",
    "I_F_giveaways",
    "shotsBlockedByPlayer",
]

TOTAL_STAT_RENAMES = {
    "icetime": "total_icetime",
    "I_F_goals": "total_goals",
    "I_F_primaryAssists": "total_primary_assists",
    "I_F_secondaryAssists": "total_secondary_assists",
    "I_F_points": "total_points",
    "I_F_shotsOnGoal": "total_shots",
    "I_F_hits": "total_hits",
    "I_F_takeaways": "total_takeaways",
    "I_F_giveaways": "total_giveaways",
    "shotsBlockedByPlayer": "total_blocks",
}


def load_skater_data():
    """
    Load the MoneyPuck skater CSV file into a pandas DataFrame.

    A DataFrame is like a spreadsheet inside Python:
    - rows are records
    - columns are pieces of information
    """
    skater_data = pd.read_csv(DATA_FILE_PATH)
    return skater_data


def print_dataset_summary(skater_data):
    """
    Print beginner-friendly information about the dataset.

    We are only inspecting the data in Milestone 1.
    We are not cleaning, changing, or deleting anything yet.
    """
    print("MILESTONE 1: DATASET CHECK")
    print("==========================")

    print("\nNumber of rows:")
    print(len(skater_data))

    print("\nNumber of columns:")
    print(len(skater_data.columns))

    print("\nAll column names:")
    print(list(skater_data.columns))

    print("\nFirst 5 rows:")
    print(skater_data.head())

    print("\nUnique seasons:")
    print(sorted(skater_data["season"].unique()))

    print("\nUnique teams:")
    print(sorted(skater_data["team"].dropna().unique()))

    print("\nUnique situations:")
    print(sorted(skater_data["situation"].dropna().unique()))


def clean_skater_data(skater_data):
    """
    Create a simpler dataset for Version 1.

    Cleaning means:
    - keep only the '5on5' situation for the main card
    - keep only the columns we need right now
    - remove rows that are missing a player name
    """
    even_strength_only = skater_data[skater_data["situation"] == "5on5"]

    cleaned_skater_data = even_strength_only[COLUMNS_TO_KEEP]

    cleaned_skater_data = cleaned_skater_data.dropna(subset=["name"])

    return cleaned_skater_data


def add_all_situation_basic_stats(skater_data, cleaned_skater_data):
    """
    Add full-season totals to the 5-on-5 player rows.

    Basic counting stats should use all situations:
    - even strength
    - power play
    - penalty kill

    Percentiles and On-Ice xG% still use the 5-on-5 row.
    """
    all_situations_data = skater_data[skater_data["situation"] == "all"].copy()

    total_stats = all_situations_data[TOTAL_STATS_TO_KEEP]
    total_stats = total_stats.rename(columns=TOTAL_STAT_RENAMES)
    total_stats["total_toi_per_game"] = (
        total_stats["total_icetime"] / all_situations_data["games_played"] / 60
    ).round(2)

    skater_data_with_totals = cleaned_skater_data.merge(
        total_stats,
        on=["playerId", "season", "team"],
        how="left",
    )

    return skater_data_with_totals


def get_special_teams_stats(skater_data, situation, prefix):
    """
    Calculate special-teams stats for one situation.

    5on4 is power play.
    4on5 is penalty kill.
    """
    situation_data = skater_data[skater_data["situation"] == situation].copy()

    situation_data[f"{prefix}_toi_per_game"] = (
        situation_data["icetime"] / situation_data["games_played"] / 60
    ).round(2)
    situation_data[f"{prefix}_goals"] = situation_data["I_F_goals"]
    situation_data[f"{prefix}_points"] = situation_data["I_F_points"]
    situation_data[f"{prefix}_shots"] = situation_data["I_F_shotsOnGoal"]
    situation_data[f"{prefix}_xgoals"] = situation_data["I_F_xGoals"]
    situation_data[f"{prefix}_on_ice_xgoals"] = situation_data["OnIce_F_xGoals"]
    situation_data[f"{prefix}_on_ice_xgoals_percentage"] = (
        situation_data["OnIce_F_xGoals"]
        / (situation_data["OnIce_F_xGoals"] + situation_data["OnIce_A_xGoals"])
    ).round(3)
    situation_data[f"{prefix}_points_per_60"] = (
        situation_data["I_F_points"] / situation_data["icetime"] * 3600
    ).round(2)
    situation_data[f"{prefix}_blocks"] = situation_data["shotsBlockedByPlayer"]
    situation_data[f"{prefix}_takeaways"] = situation_data["I_F_takeaways"]
    situation_data[f"{prefix}_xgoals_against_per_60"] = (
        situation_data["OnIce_A_xGoals"] / situation_data["icetime"] * 3600
    ).round(2)

    special_teams_columns = [
        f"{prefix}_toi_per_game",
        f"{prefix}_goals",
        f"{prefix}_points",
        f"{prefix}_shots",
        f"{prefix}_xgoals",
        f"{prefix}_on_ice_xgoals",
        f"{prefix}_on_ice_xgoals_percentage",
        f"{prefix}_points_per_60",
        f"{prefix}_blocks",
        f"{prefix}_takeaways",
        f"{prefix}_xgoals_against_per_60",
    ]

    situation_data.loc[situation_data["icetime"] <= 0, special_teams_columns] = pd.NA

    return situation_data[["playerId", "season", "team"] + special_teams_columns]


def add_special_teams_toi_per_game(skater_data, cleaned_skater_data):
    """
    Add power-play and penalty-kill stats.
    """
    pp_data = get_special_teams_stats(
        skater_data,
        "5on4",
        "pp",
    )
    pk_data = get_special_teams_stats(
        skater_data,
        "4on5",
        "pk",
    )

    skater_data_with_special_teams = cleaned_skater_data.merge(
        pp_data,
        on=["playerId", "season", "team"],
        how="left",
    )
    skater_data_with_special_teams = skater_data_with_special_teams.merge(
        pk_data,
        on=["playerId", "season", "team"],
        how="left",
    )

    return skater_data_with_special_teams


def save_cleaned_data(cleaned_skater_data):
    """
    Save the cleaned DataFrame as a new CSV file.

    index=False means pandas should not add an extra row-number column.
    """
    cleaned_skater_data.to_csv(CLEANED_DATA_FILE_PATH, index=False)


def save_per_game_data(per_game_skater_data):
    """
    Save the DataFrame that includes per-game stats.
    """
    per_game_skater_data.to_csv(PER_GAME_DATA_FILE_PATH, index=False)


def save_per_60_data(per_60_skater_data):
    """
    Save the DataFrame that includes per-game and per-60 stats.
    """
    per_60_skater_data.to_csv(PER_60_DATA_FILE_PATH, index=False)


def save_percentile_data(percentile_skater_data):
    """
    Save the DataFrame that includes percentile rankings.
    """
    percentile_skater_data.to_csv(PERCENTILE_DATA_FILE_PATH, index=False)


def save_strengths_data(strengths_skater_data):
    """
    Save the DataFrame that includes strengths and weaknesses.
    """
    strengths_skater_data.to_csv(STRENGTHS_DATA_FILE_PATH, index=False)


def print_cleaning_summary(original_data, cleaned_data):
    """
    Print a simple before-and-after summary.
    """
    print("MILESTONE 3: CLEAN DATA")
    print("=======================")

    print("\nOriginal rows:")
    print(len(original_data))

    print("\nCleaned rows:")
    print(len(cleaned_data))

    print("\nOriginal columns:")
    print(len(original_data.columns))

    print("\nCleaned columns:")
    print(len(cleaned_data.columns))

    print("\nCleaned column names:")
    print(list(cleaned_data.columns))

    print("\nCleaned situations:")
    print(sorted(cleaned_data["situation"].unique()))

    print("\nFirst 5 cleaned rows:")
    print(cleaned_data.head())

    print("\nCleaned file saved here:")
    print(CLEANED_DATA_FILE_PATH)


def print_per_game_summary(per_game_data):
    """
    Print a small preview of the new per-game stats.
    """
    per_game_columns = [
        "name",
        "team",
        "games_played",
        "goals_per_game",
        "points_per_game",
        "shots_per_game",
        "expected_goals_per_game",
        "hits_per_game",
        "blocks_per_game",
    ]

    print("\nMILESTONE 4: PER-GAME STATS")
    print("===========================")

    print("\nNew per-game columns:")
    print(
        [
            "goals_per_game",
            "primary_assists_per_game",
            "secondary_assists_per_game",
            "points_per_game",
            "shots_per_game",
            "expected_goals_per_game",
            "hits_per_game",
            "takeaways_per_game",
            "giveaways_per_game",
            "blocks_per_game",
        ]
    )

    print("\nFirst 5 rows with per-game stats:")
    print(per_game_data[per_game_columns].head())

    print("\nPer-game file saved here:")
    print(PER_GAME_DATA_FILE_PATH)


def print_per_60_summary(per_60_data):
    """
    Print a small preview of the new per-60 stats.
    """
    per_60_columns = [
        "name",
        "team",
        "icetime",
        "goals_per_60",
        "points_per_60",
        "shots_per_60",
        "expected_goals_per_60",
        "hits_per_60",
        "blocks_per_60",
    ]

    print("\nMILESTONE 5: PER-60 STATS")
    print("=========================")

    print("\nNew per-60 columns:")
    print(
        [
            "goals_per_60",
            "points_per_60",
            "shots_per_60",
            "expected_goals_per_60",
            "hits_per_60",
            "takeaways_per_60",
            "giveaways_per_60",
            "blocks_per_60",
        ]
    )

    print("\nFirst 5 rows with per-60 stats:")
    print(per_60_data[per_60_columns].head())

    print("\nPer-60 file saved here:")
    print(PER_60_DATA_FILE_PATH)


def print_percentile_summary(percentile_data):
    """
    Print a small preview of the new percentile rankings.
    """
    percentile_columns = [
        "name",
        "team",
        "points_per_game_percentile",
        "points_per_60_percentile",
        "expected_goals_per_60_percentile",
        "onIce_xGoalsPercentage_percentile",
    ]

    print("\nMILESTONE 6: PERCENTILE RANKINGS")
    print("================================")

    print("\nStats we ranked:")
    print(PERCENTILE_STATS)

    print("\nFirst 5 rows with percentile rankings:")
    print(percentile_data[percentile_columns].head())

    print("\nPercentile file saved here:")
    print(PERCENTILE_DATA_FILE_PATH)


def print_strengths_summary(strengths_data):
    """
    Print a small preview of strengths and weaknesses.
    """
    strengths_columns = [
        "name",
        "team",
        "strengths",
        "weaknesses",
    ]

    print("\nMILESTONE 7: STRENGTHS AND WEAKNESSES")
    print("=====================================")

    print("\nFirst 5 rows with strengths and weaknesses:")
    print(strengths_data[strengths_columns].head())

    print("\nStrengths file saved here:")
    print(STRENGTHS_DATA_FILE_PATH)


def main():
    """
    Run the Milestone 3 cleaning step.

    Python starts here when we run:
    python clean_data.py
    """
    skater_data = load_skater_data()
    cleaned_skater_data = clean_skater_data(skater_data)
    basic_totals_skater_data = add_all_situation_basic_stats(
        skater_data,
        cleaned_skater_data,
    )
    special_teams_skater_data = add_special_teams_toi_per_game(
        skater_data,
        basic_totals_skater_data,
    )
    toi_skater_data = add_toi_per_game_stats(special_teams_skater_data)
    per_game_skater_data = add_per_game_stats(toi_skater_data)
    per_60_skater_data = add_per_60_stats(per_game_skater_data)
    percentile_skater_data = add_percentile_stats(per_60_skater_data)
    strengths_skater_data = add_strengths_and_weaknesses(percentile_skater_data)

    save_cleaned_data(cleaned_skater_data)
    save_per_game_data(per_game_skater_data)
    save_per_60_data(per_60_skater_data)
    save_percentile_data(percentile_skater_data)
    save_strengths_data(strengths_skater_data)

    print_cleaning_summary(skater_data, cleaned_skater_data)
    print_per_game_summary(per_game_skater_data)
    print_per_60_summary(per_60_skater_data)
    print_percentile_summary(percentile_skater_data)
    print_strengths_summary(strengths_skater_data)


if __name__ == "__main__":
    main()
