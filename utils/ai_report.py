def is_missing(value):
    """
    Check whether a value is missing.

    In pandas, missing numbers are often NaN.
    NaN is unusual because it is not equal to itself.
    """
    return value != value


def get_stat(player, column_name):
    """
    Safely get one stat from the player row.

    If the column does not exist, return None.
    """
    if column_name not in player:
        return None

    value = player[column_name]

    if is_missing(value):
        return None

    return value


def is_high(value):
    """
    Check whether a percentile is strong.
    """
    return value is not None and value >= 70


def is_very_high(value):
    """
    Check whether a percentile is excellent.
    """
    return value is not None and value >= 85


def is_low(value):
    """
    Check whether a percentile is below average.
    """
    return value is not None and value < 35


def get_position_group(position):
    """
    Convert a position into forward or defense.
    """
    if position == "D":
        return "defense"

    return "forward"


def describe_offense(player):
    """
    Write one sentence about offensive impact.
    """
    goals_percentile = get_stat(player, "goals_per_60_percentile")
    points_percentile = get_stat(player, "points_per_60_percentile")
    shots_percentile = get_stat(player, "shots_per_60_percentile")
    expected_goals_percentile = get_stat(player, "expected_goals_per_60_percentile")
    pp_toi_per_game = get_stat(player, "pp_toi_per_game")
    pp_points = get_stat(player, "pp_points")

    if is_very_high(points_percentile) and is_high(goals_percentile):
        sentence = "Offensively, he profiles as a high-end scorer with strong finishing and point-production indicators."
    elif is_high(points_percentile) and not is_high(goals_percentile):
        sentence = "Offensively, he profiles more as a playmaker than a pure finisher."
    elif is_high(goals_percentile):
        sentence = "Offensively, he shows a goal-scoring lean, with his finishing standing out more than his overall production."
    elif is_low(points_percentile):
        sentence = "Offensively, his production profile is limited compared with players in a similar role."
    else:
        sentence = "Offensively, he provides a balanced but not dominant scoring profile."

    if is_high(expected_goals_percentile):
        sentence += " His chance-quality profile suggests he gets to dangerous areas."
    elif is_high(shots_percentile):
        sentence += " He creates offense more through shot volume than chance quality."

    if pp_toi_per_game is not None and pp_toi_per_game >= 1 and pp_points is not None and pp_points > 0:
        sentence += " He also contributes on the power play."

    return sentence


def describe_even_strength(player):
    """
    Write one sentence about 5-on-5 impact.
    """
    on_ice_xg_percentile = get_stat(player, "onIce_xGoalsPercentage_percentile")
    corsi_percentile = get_stat(player, "onIce_corsiPercentage_percentile")
    fenwick_percentile = get_stat(player, "onIce_fenwickPercentage_percentile")

    if is_high(on_ice_xg_percentile) and is_high(corsi_percentile):
        return "At 5-on-5, his team tends to tilt the ice in his minutes, controlling both shot share and quality chances."

    if is_high(on_ice_xg_percentile):
        return "At 5-on-5, his strongest impact is in the quality of chances his team creates while he is on the ice."

    if is_high(corsi_percentile) or is_high(fenwick_percentile):
        return "At 5-on-5, the shot-share results are positive, even if the chance-quality impact is less clear."

    if is_low(on_ice_xg_percentile):
        return "At 5-on-5, the expected-goals results are a concern and suggest his minutes have not consistently tilted play positively."

    return "At 5-on-5, his on-ice impact looks closer to average than clearly play-driving."


def describe_defense(player):
    """
    Write one sentence about defensive impact.
    """
    on_ice_xg_percentile = get_stat(player, "onIce_xGoalsPercentage_percentile")
    blocks_percentile = get_stat(player, "blocks_per_60_percentile")
    pk_toi_per_game = get_stat(player, "pk_toi_per_game")
    pk_blocks = get_stat(player, "pk_blocks")

    if is_high(on_ice_xg_percentile):
        sentence = "Defensively, the 5-on-5 results are supportive, with his overall expected-goals share pointing toward reliable territorial impact."
    elif is_low(on_ice_xg_percentile):
        sentence = "Defensively, the profile is less convincing because the 5-on-5 expected-goals results are below average."
    else:
        sentence = "Defensively, the results are more neutral than standout."

    if is_high(blocks_percentile):
        sentence += " He also adds value as a shot blocker."

    if pk_toi_per_game is not None and pk_toi_per_game >= 1:
        sentence += " His penalty-kill usage points to some defensive trust."
    elif pk_blocks is not None and pk_blocks > 0:
        sentence += " He has contributed in limited penalty-kill minutes."

    return sentence


def classify_role(player):
    """
    Choose a simple NHL role label from the player's statistical profile.
    """
    position_group = get_position_group(player["position"])
    points_percentile = get_stat(player, "points_per_60_percentile")
    goals_percentile = get_stat(player, "goals_per_60_percentile")
    on_ice_xg_percentile = get_stat(player, "onIce_xGoalsPercentage_percentile")
    blocks_percentile = get_stat(player, "blocks_per_60_percentile")

    if position_group == "defense":
        if is_high(points_percentile) and is_high(on_ice_xg_percentile):
            return "top-four defenseman"

        if is_high(points_percentile):
            return "offensive defenseman"

        if is_high(blocks_percentile) and not is_low(on_ice_xg_percentile):
            return "defensive defenseman"

        return "depth defenseman"

    if is_very_high(points_percentile) and is_very_high(on_ice_xg_percentile):
        return "first-line forward"

    if is_high(points_percentile) and is_high(goals_percentile):
        return "top-six scoring winger"

    if is_high(points_percentile):
        return "top-six playmaker"

    if not is_low(points_percentile) and not is_low(on_ice_xg_percentile):
        return "middle-six forward"

    if is_high(blocks_percentile):
        return "defensive specialist"

    return "depth player"


def generate_scouting_report(player):
    """
    Generate a concise professional scouting report from provided stats only.
    """
    offensive_sentence = describe_offense(player)
    even_strength_sentence = describe_even_strength(player)
    defensive_sentence = describe_defense(player)
    role = classify_role(player)

    role_sentence = (
        f"Overall, his statistical profile fits best as a {role}."
    )

    return " ".join(
        [
            offensive_sentence,
            even_strength_sentence,
            defensive_sentence,
            role_sentence,
        ]
    )


def generate_ai_scouting_report(player):
    """
    Keep the old function name working for any existing imports.
    """
    return generate_scouting_report(player)
