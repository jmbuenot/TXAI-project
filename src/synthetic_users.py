from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class SyntheticUser:
    """
    Simple representation of a synthetic user profile.

    Attributes
    ----------
    user_id:
        Identifier used in filenames.
    display_name:
        Human-readable description of the profile.
    genre_weights:
        Mapping from genre name (as it appears in the dataset's `genre` field)
        to a preference weight. Higher values indicate stronger preference.
    length_preference:
        One of {"short", "long", "any"} describing whether this user tends to
        prefer shorter or longer books. This is used heuristically in the
        personalised scoring function.
    """

    user_id: str
    display_name: str
    genre_weights: Dict[str, float]
    length_preference: str = "any"


def predefined_synthetic_users() -> Dict[str, SyntheticUser]:
    """
    Return a small library of hand-crafted synthetic user profiles.

    These profiles are intended for demonstration and analysis only; they do
    not correspond to real users.
    """
    return {
        "fantasy_fan": SyntheticUser(
            user_id="fantasy_fan",
            display_name="Fantasy & Sci-Fi Enthusiast",
            genre_weights={
                "Fantasy": 1.0,
                "Science Fiction": 0.9,
                "Young Adult": 0.6,
                "Sequential Art": 0.5,
            },
            length_preference="long",
        ),
        "literary_reader": SyntheticUser(
            user_id="literary_reader",
            display_name="Literary Fiction & Classics Reader",
            genre_weights={
                "Fiction": 1.0,
                "European Literature": 0.9,
                "Novels": 0.7,
                "Nonfiction": 0.3,
            },
            length_preference="any",
        ),
        "nonfiction_learner": SyntheticUser(
            user_id="nonfiction_learner",
            display_name="Nonfiction & Academic Reader",
            genre_weights={
                "Nonfiction": 1.0,
                "History": 0.9,
                "Academic": 0.8,
                "Art": 0.5,
            },
            length_preference="long",
        ),
        "romance_reader": SyntheticUser(
            user_id="romance_reader",
            display_name="Romance & Contemporary Reader",
            genre_weights={
                "Romance": 1.0,
                "Category Romance": 0.9,
                "Contemporary": 0.7,
                "Fiction": 0.4,
            },
            length_preference="short",
        ),
        "kids_parent": SyntheticUser(
            user_id="kids_parent",
            display_name="Children's & YA Parent",
            genre_weights={
                "Childrens": 1.0,
                "Young Adult": 0.8,
                "Animals": 0.7,
                "Sequential Art": 0.4,
            },
            length_preference="short",
        ),
    }


