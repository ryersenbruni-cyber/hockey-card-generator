def add_per_game_stats(skater_data):
    """
    Add per-game stats to the skater dataset.

    Per-game stats help us compare players who played different numbers
    of games.
    """
    skater_data = skater_data.copy()

    skater_data["goals_per_game"] = (
        skater_data["I_F_goals"] / skater_data["games_played"]
    ).round(2)

    skater_data["primary_assists_per_game"] = (
        skater_data["I_F_primaryAssists"] / skater_data["games_played"]
    ).round(2)

    skater_data["secondary_assists_per_game"] = (
        skater_data["I_F_secondaryAssists"] / skater_data["games_played"]
    ).round(2)

    skater_data["points_per_game"] = (
        skater_data["I_F_points"] / skater_data["games_played"]
    ).round(2)

    skater_data["shots_per_game"] = (
        skater_data["I_F_shotsOnGoal"] / skater_data["games_played"]
    ).round(2)

    skater_data["expected_goals_per_game"] = (
        skater_data["I_F_xGoals"] / skater_data["games_played"]
    ).round(2)

    skater_data["hits_per_game"] = (
        skater_data["I_F_hits"] / skater_data["games_played"]
    ).round(2)

    skater_data["takeaways_per_game"] = (
        skater_data["I_F_takeaways"] / skater_data["games_played"]
    ).round(2)

    skater_data["giveaways_per_game"] = (
        skater_data["I_F_giveaways"] / skater_data["games_played"]
    ).round(2)

    skater_data["blocks_per_game"] = (
        skater_data["shotsBlockedByPlayer"] / skater_data["games_played"]
    ).round(2)

    return skater_data


def add_toi_per_game_stats(skater_data):
    """
    Add time-on-ice per game in minutes.

    MoneyPuck ice time is stored in seconds.
    We divide by 60 to turn seconds into minutes.
    """
    skater_data = skater_data.copy()

    skater_data["toi_per_game"] = (
        skater_data["icetime"] / skater_data["games_played"] / 60
    ).round(2)

    return skater_data


def calculate_per_60(stat_column, icetime_column):
    """
    Calculate a per-60-minute stat.

    MoneyPuck ice time is stored in seconds.
    There are 3,600 seconds in 60 minutes.
    """
    return (stat_column / icetime_column * 3600).round(2)


def add_per_60_stats(skater_data):
    """
    Add per-60-minute stats to the skater dataset.

    Per-60 stats help us compare players by ice time instead of games played.
    """
    skater_data = skater_data.copy()

    skater_data["goals_per_60"] = calculate_per_60(
        skater_data["I_F_goals"],
        skater_data["icetime"],
    )

    skater_data["points_per_60"] = calculate_per_60(
        skater_data["I_F_points"],
        skater_data["icetime"],
    )

    skater_data["shots_per_60"] = calculate_per_60(
        skater_data["I_F_shotsOnGoal"],
        skater_data["icetime"],
    )

    skater_data["expected_goals_per_60"] = calculate_per_60(
        skater_data["I_F_xGoals"],
        skater_data["icetime"],
    )

    skater_data["on_ice_xgoals_for_per_60"] = calculate_per_60(
        skater_data["OnIce_F_xGoals"],
        skater_data["icetime"],
    )

    skater_data["on_ice_xgoals_against_per_60"] = calculate_per_60(
        skater_data["OnIce_A_xGoals"],
        skater_data["icetime"],
    )

    skater_data["hits_per_60"] = calculate_per_60(
        skater_data["I_F_hits"],
        skater_data["icetime"],
    )

    skater_data["takeaways_per_60"] = calculate_per_60(
        skater_data["I_F_takeaways"],
        skater_data["icetime"],
    )

    skater_data["giveaways_per_60"] = calculate_per_60(
        skater_data["I_F_giveaways"],
        skater_data["icetime"],
    )

    skater_data["blocks_per_60"] = calculate_per_60(
        skater_data["shotsBlockedByPlayer"],
        skater_data["icetime"],
    )

    return skater_data
