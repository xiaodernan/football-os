"""Fictional identity vocabulary for the generated world.

Every name is assembled from consonant-vowel tables rather than taken from any roster,
league table or directory, so the world cannot describe a real person, club or place
(`DATA_POLICY.md` §2). The palettes are deliberately unusual — a name should read as
generated at first glance, which is what spec §65 asks for.
"""

from __future__ import annotations

import re
from typing import Final

from app.services.world.rng import WorldRng

_GIVEN_ONSET: Final = (
    "ad",
    "bal",
    "cor",
    "dax",
    "el",
    "far",
    "gar",
    "hin",
    "jan",
    "ka",
    "lor",
    "mir",
    "no",
    "or",
    "pel",
    "qua",
    "ran",
    "sa",
    "tor",
    "un",
    "va",
    "wren",
    "xan",
    "yor",
    "ze",
)
_GIVEN_CODA: Final = (
    "and",
    "ek",
    "iel",
    "in",
    "or",
    "a",
    "us",
    "yn",
    "eth",
    "iva",
    "olo",
    "une",
    "ash",
    "ira",
    "um",
)
_FAMILY_STEM: Final = (
    "van",
    "mor",
    "kresh",
    "dol",
    "har",
    "qel",
    "sor",
    "tan",
    "fenn",
    "lau",
    "gen",
    "drost",
    "veit",
    "bryn",
    "cale",
    "ovar",
    "siel",
    "ruce",
    "zeph",
    "marn",
    "tob",
    "eld",
    "wyn",
    "kast",
)
_FAMILY_END: Final = ("tis", "ek", "ard", "ino", "ova", "er", "an", "ith", "mann", "oux", "elli", "berg")

_PLACE_STEM: Final = (
    "kal",
    "vire",
    "thorn",
    "mel",
    "obr",
    "eln",
    "dur",
    "var",
    "lyn",
    "cor",
    "fest",
    "hald",
    "wyr",
    "ost",
    "brae",
    "dun",
    "quern",
    "ild",
    "rav",
    "silm",
)
_PLACE_TAIL: Final = ("dera", "mont", "wick", "ford", "moor", "haven", "stead", "hurst", "dale", "gard")
_CLUB_SUFFIX: Final = (
    "Union",
    "Athletic",
    "Rovers",
    "Albion",
    "Town",
    "Sporting",
    "Wanderers",
    "Metropolitan",
    "Naval",
    "Miners",
)
_STAND_SUFFIX: Final = ("Park", "Ridge", "Grounds", "Arena", "Bowl", "Field", "Terrace", "Yard")
_NATION_TAIL: Final = ("ovia", "ara", "enheim", "istan", "eid", "ora", "yth")

# Only shapes `builder.XI_BY_FORMATION` can actually field a seeded squad with.
_FORMATIONS: Final = ("4-4-2", "4-2-3-1", "4-3-3")

_COLOURS: Final = (
    "#1f6f5c",
    "#8c2f39",
    "#1d4e89",
    "#c8791b",
    "#4b3f72",
    "#0f6d63",
    "#93441f",
    "#2f4858",
    "#7a5195",
    "#145a32",
    "#8a6d3b",
    "#3b4a6b",
)
_LEAGUE_WORDS: Final = ("Premier Division", "Elite League", "First Tier", "Superleague")
_CUP_WORDS: Final = ("Invitation Cup", "Charity Shield", "Grand Cup", "Super Cup", "Alliance Trophy", "Harbour Cup")


def _cap(value: str) -> str:
    return value[:1].upper() + value[1:]


def slugify(value: str) -> str:
    """URL-safe identity for a world row: lowercase, hyphenated, ASCII (spec §80)."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "unnamed"


def person_name(rng: WorldRng) -> str:
    given = _cap(rng.choice(_GIVEN_ONSET) + rng.choice(_GIVEN_CODA))
    family = _cap(rng.choice(_FAMILY_STEM) + rng.choice(_FAMILY_END))
    return f"{given} {family}"


def place_name(rng: WorldRng) -> str:
    return _cap(rng.choice(_PLACE_STEM) + rng.choice(_PLACE_TAIL))


def club_name(rng: WorldRng) -> tuple[str, str, str]:
    """Return `(club name, city, short code)` for one fictional team."""
    city = place_name(rng)
    suffix = rng.choice(_CLUB_SUFFIX)
    short = (city[:3] + suffix[:1]).upper()
    return f"{city} {suffix}", city, short


def stadium_name(rng: WorldRng, city: str) -> str:
    return f"{city} {rng.choice(_STAND_SUFFIX)}"


def nation_name(rng: WorldRng) -> str:
    return _cap(rng.choice(_PLACE_STEM) + rng.choice(_NATION_TAIL))


def region_name(rng: WorldRng) -> str:
    return place_name(rng)


def competition_name(rng: WorldRng, region: str, kind: str) -> str:
    word = rng.choice(_LEAGUE_WORDS if kind == "league" else _CUP_WORDS)
    return f"{region} {word}"


def brand_colour(rng: WorldRng) -> str:
    return rng.choice(_COLOURS)


def formation(rng: WorldRng) -> str:
    return rng.choice(_FORMATIONS)


__all__ = [
    "brand_colour",
    "club_name",
    "competition_name",
    "formation",
    "nation_name",
    "person_name",
    "place_name",
    "region_name",
    "slugify",
    "stadium_name",
]
