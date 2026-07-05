def calculate_win_rate(wins: int, losses: int) -> float:
    """Standardized win rate calculation using only resolved trades."""
    resolved = wins + losses
    if resolved == 0:
        return 0.0
    return round((wins / resolved) * 100, 1)
