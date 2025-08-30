# core/dice.py
import random
import re

def roll_dice(expr: str) -> dict:
    """
    ndm ダイスを振る (例: '2d6', '1d100', '3d8')
    """
    match = re.match(r"(\d*)d(\d+)", expr.strip().lower())
    if not match:
        raise ValueError(f"無効なダイス式: {expr}")

    n = int(match.group(1) or 1)
    m = int(match.group(2))

    dice = [random.randint(1, m) for _ in range(n)]
    total = sum(dice)
    return {"dice": dice, "total": total, "sides": m, "count": n}

