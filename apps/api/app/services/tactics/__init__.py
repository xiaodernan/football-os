"""Tactical Lab services (spec §11–§13, §65): shapes, roles, measured geometry, the 50-system catalogue.

Layering, in the order that keeps each level testable on its own:

``pitch``   metres and geometry, no knowledge of football vocabulary
``roles``   what a slot is asked to do, in and out of possession
``shapes``  ten authored formations × five temperaments — the only hand-written coordinates
``analysis`` the transforms from those coordinates, the eight metrics, and named counterfactuals
``plan``    the 50 systems, each graded against the catalogue's own distribution
``sync``    store the plan and refuse to leave half a catalogue behind
"""

from app.services.tactics.analysis import (
    CHANGES,
    METRIC_KEYS,
    Change,
    Metric,
    Shape,
    ShapeDiff,
    analyse,
    apply_change,
    in_possession,
    metrics_of,
    out_of_possession,
    shape_from_rows,
)
from app.services.tactics.pitch import Point, centroid, clamp_point, distance, lane_of, nearest_neighbour_distances, third_of, zone_of
from app.services.tactics.plan import (
    SYSTEM_COUNT,
    PlannedSystem,
    fingerprint,
    metric_value,
    planned_rows,
    system_by_key,
    system_by_slug,
    system_path,
    tactical_problems,
    tactical_systems,
)
from app.services.tactics.roles import BANDS, ROLES, TACTICAL_ATTRIBUTES, Role
from app.services.tactics.shapes import FORMATION_SHAPES, TEMPERAMENTS, Slot, Temperament
from app.services.tactics.sync import (
    TACTICS_GATE,
    TacticsSyncReport,
    stored_system,
    sync_tactics,
    tactics_counts,
    tactics_ready,
    tactics_tables_present,
)

__all__ = [
    "BANDS",
    "CHANGES",
    "FORMATION_SHAPES",
    "METRIC_KEYS",
    "ROLES",
    "SYSTEM_COUNT",
    "TACTICAL_ATTRIBUTES",
    "TACTICS_GATE",
    "TEMPERAMENTS",
    "Change",
    "Metric",
    "PlannedSystem",
    "Point",
    "Role",
    "Shape",
    "ShapeDiff",
    "Slot",
    "TacticsSyncReport",
    "Temperament",
    "analyse",
    "apply_change",
    "centroid",
    "clamp_point",
    "distance",
    "fingerprint",
    "in_possession",
    "lane_of",
    "metric_value",
    "metrics_of",
    "nearest_neighbour_distances",
    "out_of_possession",
    "planned_rows",
    "shape_from_rows",
    "stored_system",
    "sync_tactics",
    "system_by_key",
    "system_by_slug",
    "system_path",
    "tactical_problems",
    "tactical_systems",
    "tactics_counts",
    "tactics_ready",
    "tactics_tables_present",
    "third_of",
    "zone_of",
]
