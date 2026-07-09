PERCENTILE_STATS = [
    "points_per_game",
    "goals_per_60",
    "points_per_60",
    "shots_per_60",
    "expected_goals_per_60",
    "hits_per_60",
    "takeaways_per_60",
    "blocks_per_60",
    "onIce_xGoalsPercentage",
    "onIce_corsiPercentage",
    "onIce_fenwickPercentage",
]


def get_position_group(position):
    """
    Convert a player's exact position into a comparison group.

    D means defenseman.
    F means forward, which includes C, L, and R.
    """
    if position == "D":
        return "D"

    return "F"


def add_position_groups(skater_data):
    """
    Add a simple position group column.

    This lets us compare:
    - defensemen against defensemen
    - forwards against forwards
    """
    skater_data["position_group"] = skater_data["position"].apply(get_position_group)

    return skater_data


def add_percentile_for_column(skater_data, column_name):
    """
    Add one percentile column for one stat.

    Example:
    points_per_game becomes points_per_game_percentile.
    """
    percentile_column_name = column_name + "_percentile"

    skater_data[percentile_column_name] = (
        skater_data.groupby(["season", "position_group"])[column_name].rank(pct=True)
        * 100
    ).round(0)

    return skater_data


def add_percentile_stats(skater_data):
    """
    Add percentile rankings for our Version 1 card stats.

    A percentile is a 0-100 ranking.
    Higher is better for the stats we are using in Version 1.
    """
    skater_data = skater_data.copy()
    skater_data = add_position_groups(skater_data)

    for column_name in PERCENTILE_STATS:
        skater_data = add_percentile_for_column(skater_data, column_name)

    return skater_data
