"""Item categories shared by the listing agent and the matcher."""

CATEGORIES = (
    "furniture",
    "appliances",
    "electronics",
    "textbooks",
    "kitchen",
    "clothing",
    "decor",
    "bikes-transport",
    "sports-outdoors",
    "other",
)


def neighbours(category: str) -> tuple[str, ...]:
    """Categories worth searching for a match. The model sometimes files the same item
    differently on each side, so "other" is always searched, and an "other" item is
    compared against everything."""
    if category not in CATEGORIES or category == "other":
        return CATEGORIES
    return (category, "other")
