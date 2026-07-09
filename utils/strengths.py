STRENGTH_THRESHOLD = 75
WEAKNESS_THRESHOLD = 25

STAT_LABELS = {
    "points_per_game_percentile": "point production",
    "goals_per_60_percentile": "goal scoring rate",
    "points_per_60_percentile": "scoring efficiency",
    "shots_per_60_percentile": "shot generation",
    "expected_goals_per_60_percentile": "chance quality",
    "hits_per_60_percentile": "physical play",
    "takeaways_per_60_percentile": "puck takeaways",
    "blocks_per_60_percentile": "shot blocking",
    "onIce_xGoalsPercentage_percentile": "expected-goals impact",
    "onIce_corsiPercentage_percentile": "shot-attempt impact",
    "onIce_fenwickPercentage_percentile": "unblocked-shot impact",
}


def find_strengths_for_player(player_row):
    """
    Find the player's strongest areas.

    A strength is any stat at or above the 75th percentile.
    """
    strengths = []

    for percentile_column, readable_label in STAT_LABELS.items():
        if player_row[percentile_column] >= STRENGTH_THRESHOLD:
            strengths.append(readable_label)

    if not strengths:
        strengths.append("No standout strength yet")

    return ", ".join(strengths)


def find_weaknesses_for_player(player_row):
    """
    Find the player's weakest areas.

    A weakness is any stat at or below the 25th percentile.
    """
    weaknesses = []

    for percentile_column, readable_label in STAT_LABELS.items():
        if player_row[percentile_column] <= WEAKNESS_THRESHOLD:
            weaknesses.append(readable_label)

    if not weaknesses:
        weaknesses.append("No major weakness flagged")

    return ", ".join(weaknesses)


def add_strengths_and_weaknesses(skater_data):
    """
    Add strengths and weaknesses columns to the dataset.
    """
    skater_data = skater_data.copy()

    skater_data["strengths"] = skater_data.apply(find_strengths_for_player, axis=1)
    skater_data["weaknesses"] = skater_data.apply(find_weaknesses_for_player, axis=1)

    return skater_data
