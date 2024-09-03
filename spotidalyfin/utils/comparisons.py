from difflib import SequenceMatcher


def similar(a: str, b: str, ratio: float = 0.9) -> bool:
    """Check if two strings are similar based on a ratio threshold."""
    return SequenceMatcher(None, a, b).ratio() > ratio


def close(a: int, b: int, delta: int = 2) -> bool:
    """Check if two numbers are within a specified range."""
    return abs(a - b) < delta
