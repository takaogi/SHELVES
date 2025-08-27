# core/dice.py
import random

def roll_2d6() -> dict:
    """2d6を振って結果を返す"""
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    return {"dice": [dice1, dice2], "total": total}
