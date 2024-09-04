import re
from collections import Counter


def close(a: int | float, b: int | float, delta: int = 2) -> bool | float:
    """Check if two numbers are within a specified range."""
    return abs(a - b) < delta


def weighted_word_overlap(a: str, b: str) -> float:
    """Calculate the weighted word overlap between two album titles."""

    def normalize(text: str) -> list[str]:
        """Normalize text by tokenizing, converting to lowercase, and removing stopwords and non-alphanumeric characters."""
        tokens = text.lower().split()
        tokens = [re.sub(r'\W+', '', token) for token in tokens]  # Remove non-alphanumeric characters
        tokens = [token for token in tokens if token != '']
        return tokens

    tokens_a = normalize(a)
    tokens_b = normalize(b)

    if not tokens_a or not tokens_b:
        return 0.0

    counter_a = Counter(tokens_a)
    counter_b = Counter(tokens_b)

    # Calculate the total number of words and common words
    total_words = sum((counter_a | counter_b).values())  # Union of counters
    common_words = sum((counter_a & counter_b).values())  # Intersection of counters

    # Weighted ratio based on common words and total words
    return common_words / total_words
