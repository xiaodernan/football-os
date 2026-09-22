"""Tactical Lab services (spec §11–§13, §65): shapes, roles, measured geometry, the 50-system catalogue.

Layering, in the order that keeps each level testable on its own:

``pitch``   metres and geometry, no knowledge of football vocabulary
``roles``   what a slot is asked to do, in and out of possession
``shapes``  ten authored formations × five temperaments — the only hand-written coordinates
``analysis`` the transforms from those coordinates, the seven metrics, and named counterfactuals
``plan``    the 50 systems, each graded against the catalogue's own distribution
"""

from app.services.tactics.analysis import CHANGES, Change, Metric, Shape, ShapeDiff, analyse, apply_change, in_possession, metrics_of, out_of_possession
from app.services.tactics.pitch import Point, centroid, clamp_point, distance, lane_of, nearest_neighbour_distances, third_of, zone_of
from app.services.tactics.plan import (
    SYSTEM_COUNT,
    TacticalSystem,
    fingerprint,
    planned_rows,
    system_by_key,
    system_by_slug,
    system_path,
    tactical_problems,
    tactical_systems,
)
from app.services.tactics.roles import ROLES, Role
from app.services.tactics.shapes import FORMATION_SHAPES, TEMPERAMENTS, Slot, Temperament

__all__ = [
    "CHANGES",
    "FORMATION_SHAPES",
    "ROLES",
    "SYSTEM_COUNT",
    "TEMPERAMENTS",
    "Change",
    "Metric",
    "Point",
    "Role",
    "Shape",
    "ShapeDiff",
    "Slot",
    "TacticalSystem",
    "Temperament",
    "analyse",
    "apply_change",
    "centroid",
    "clamp_point",
    "distance",
    "fingerprint",
    "in_possession",
    "lane_of",
    "metrics_of",
    "nearest_neighbour_distances",
    "out_of_possession",
    "planned_rows",
    "system_by_key",
    "system_by_slug",
    "system_path",
    "tactical_problems",
    "tactical_systems",
    "third_of",
    "zone_of",
]
