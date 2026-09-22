"""The demo vision provider: statistics of real pixels, with no claim to see football (spec §14, §45, §62).

There is no model here and none is pretended. Each frame is decoded from the PPM that `media.py`
extracted and reduced to two things: how much of it is pitch-green, and where its non-pitch pixels
are — a luminance-weighted centroid. Comparing consecutive samples gives movement, with a shift, a
speed and a confidence, and every threshold and formula travels with the result, together with the
sentence saying what this cannot do.

It does not know players, a ball, a formation or a football event. It reports pixel change, which is
exactly what a clip with a known moving target lets a test verify. A licensed or trained vision model
would replace this class behind the same `VisionProvider` interface and return the same event shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

__all__ = ["DemoVisionProvider", "GridStats", "frame_stats", "motion_between", "read_ppm"]

GRID: Final = 4
BRIGHT_LUMA: Final = 190.0
GREEN_MARGIN: Final = 8
MOTION_CELL_THRESHOLD: Final = 12.0
MIN_BRIGHT_FRACTION: Final = 0.0005
MIN_CENTROID_SHIFT: Final = 0.02


@dataclass(frozen=True)
class GridStats:
    """One frame reduced to what this method can actually measure."""

    width: int
    height: int
    green_fraction: float
    luma_mean: float
    brightest_cell: tuple[int, int]
    cells: tuple[tuple[float, ...], ...]
    bright_fraction: float
    bright_centroid: tuple[float, float] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "green_fraction": round(self.green_fraction, 4),
            "luma_mean": round(self.luma_mean, 2),
            "brightest_cell": list(self.brightest_cell),
            "bright_fraction": round(self.bright_fraction, 5),
            "bright_centroid": [round(value, 4) for value in self.bright_centroid] if self.bright_centroid else None,
            "cells": [[round(value, 2) for value in row] for row in self.cells],
        }


def read_ppm(data: bytes) -> tuple[int, int, bytes]:
    """Parse a binary P6 pixmap: magic, two dimensions, max value, then RGB bytes."""
    if not data.startswith(b"P6"):
        raise ValueError("not a binary PPM (expected P6)")
    cursor = 2
    values: list[int] = []
    while len(values) < 3:
        while cursor < len(data) and data[cursor] in b" \t\r\n":
            cursor += 1
        if cursor < len(data) and data[cursor] == ord("#"):
            while cursor < len(data) and data[cursor] != ord("\n"):
                cursor += 1
            continue
        start = cursor
        while cursor < len(data) and data[cursor] not in b" \t\r\n":
            cursor += 1
        token = data[start:cursor].decode("ascii", "ignore")
        if not token.isdigit():
            raise ValueError("malformed PPM header")
        values.append(int(token))
        cursor += 1
    width, height, max_value = values
    if max_value != 255:
        raise ValueError(f"only 8-bit PPM is supported, got maxval {max_value}")
    pixels = data[cursor : cursor + width * height * 3]
    if len(pixels) < width * height * 3:
        raise ValueError("truncated PPM pixel block")
    return width, height, pixels


def frame_stats(data: bytes) -> GridStats:
    """Green fraction, a 4 × 4 grid of luma means, and the centroid of the non-pitch pixels."""
    width, height, pixels = read_ppm(data)
    total = max(1, width * height)
    green_pixels = 0
    bright_count = 0
    bright_x = 0
    bright_y = 0
    luma_total = 0.0
    cell_sums = [[0.0] * GRID for _ in range(GRID)]
    cell_counts = [[0] * GRID for _ in range(GRID)]
    for offset in range(0, len(pixels) - 2, 3):
        red, green, blue = pixels[offset], pixels[offset + 1], pixels[offset + 2]
        if green > red + GREEN_MARGIN and green > blue + GREEN_MARGIN:
            green_pixels += 1
        luma = 0.299 * red + 0.587 * green + 0.114 * blue
        luma_total += luma
        number = offset // 3
        column, row = number % width, number // width
        if luma >= BRIGHT_LUMA:
            bright_count += 1
            bright_x += column
            bright_y += row
        cell_column = min(GRID - 1, column * GRID // width)
        cell_row = min(GRID - 1, row * GRID // height)
        cell_sums[cell_row][cell_column] += luma
        cell_counts[cell_row][cell_column] += 1

    cells = tuple(tuple(cell_sums[r][c] / cell_counts[r][c] if cell_counts[r][c] else 0.0 for c in range(GRID)) for r in range(GRID))
    brightest = max(((r, c) for r in range(GRID) for c in range(GRID)), key=lambda rc: cells[rc[0]][rc[1]])
    return GridStats(
        width=width,
        height=height,
        green_fraction=green_pixels / total,
        luma_mean=luma_total / total,
        brightest_cell=brightest,
        cells=cells,
        bright_fraction=bright_count / total,
        bright_centroid=((bright_x / bright_count) / width, (bright_y / bright_count) / height) if bright_count else None,
    )


def motion_between(previous: GridStats, current: GridStats) -> dict[str, Any]:
    """Two measures, because they answer differently.

    ``changed_cells`` counts the 4 × 4 cells whose mean luma moved by at least
    ``MOTION_CELL_THRESHOLD`` — a coarse "something changed there". ``centroid_shift`` is the
    distance, in frame widths, that the centre of the non-pitch pixels moved since the previous
    sample, and it is the measure a small moving target can be trusted to: a cell mean can hide an
    object covering a twentieth of its cell, the centroid cannot.
    """
    deltas = [abs(current.cells[r][c] - previous.cells[r][c]) for r in range(GRID) for c in range(GRID)]
    changed = [[r, c] for r in range(GRID) for c in range(GRID) if abs(current.cells[r][c] - previous.cells[r][c]) >= MOTION_CELL_THRESHOLD]
    shift: float | None = None
    if previous.bright_centroid and current.bright_centroid and previous.bright_fraction >= MIN_BRIGHT_FRACTION and current.bright_fraction >= MIN_BRIGHT_FRACTION:
        shift = round(
            ((current.bright_centroid[0] - previous.bright_centroid[0]) ** 2 + (current.bright_centroid[1] - previous.bright_centroid[1]) ** 2) ** 0.5,
            4,
        )
    centroid = current.bright_centroid
    return {
        "changed_cells": changed,
        "changed_cell_count": len(changed),
        "mean_cell_delta": round(sum(deltas) / len(deltas), 2),
        "max_cell_delta": round(max(deltas), 2),
        "centroid_x": round(centroid[0], 4) if centroid else None,
        "centroid_y": round(centroid[1], 4) if centroid else None,
        "centroid_shift": shift,
        "is_movement": shift is not None and shift >= MIN_CENTROID_SHIFT,
    }


class DemoVisionProvider:
    """The self-labelled stand-in for a real vision model (spec §45: an absent key is stated, not hidden).

    `task` selects which measurement is reported, not a different model. A real provider would be
    named here once one is configured and would have to return the same event shape
    ``{t_s, kind, x, y, confidence, why}``, so the pipeline, the report and the tests stay as they are.
    """

    name = "demo-pixel-stats"

    def __init__(self, *, frame_times: list[float] | None = None, interval_s: float = 1.0) -> None:
        self.frame_times = frame_times or []
        self.interval_s = interval_s

    @property
    def demo_mode(self) -> bool:
        return True

    def analyze_frames(self, frames: list[bytes], *, task: str = "track_movement") -> dict[str, Any]:
        if not frames:
            return {
                "provider": self.name,
                "model": "ffmpeg ppm + pure-python statistics",
                "demo_mode": True,
                "task": task,
                "frames_seen": 0,
                "samples": [],
                "events": [],
                "error": "no frames were extracted, so there is nothing to measure",
                "limitations": "Nothing was measured. This is the absence of a clip, not an empty result about one.",
            }

        stats = [frame_stats(data) for data in frames]
        samples: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        for index, current in enumerate(stats):
            time_s = self.frame_times[index] if index < len(self.frame_times) else round(index * self.interval_s, 3)
            summary = current.to_dict()
            summary.pop("cells", None)
            sample: dict[str, Any] = {"index": index, "t_s": time_s, **summary}
            if index:
                previous_time = samples[index - 1]["t_s"]
                motion = motion_between(stats[index - 1], current)
                sample["motion"] = motion
                shift = motion["centroid_shift"]
                if motion["is_movement"] and shift is not None and motion["centroid_x"] is not None and motion["centroid_y"] is not None:
                    elapsed = max(1e-6, time_s - previous_time)
                    last = events[-1] if events else None
                    events.append(
                        {
                            "t_s": time_s,
                            "kind": "movement",
                            "x": motion["centroid_x"],
                            "y": motion["centroid_y"],
                            "confidence": round(min(0.99, 0.5 + shift / MIN_CENTROID_SHIFT / 8), 3),
                            "why": (f"the centre of the non-pitch pixels moved {shift:.4f} of the frame width since the previous sample, at or above the {MIN_CENTROID_SHIFT} threshold"),
                            "centroid_shift": shift,
                            "speed_frame_widths_per_s": (
                                round(
                                    ((motion["centroid_x"] - last["x"]) ** 2 + (motion["centroid_y"] - last["y"]) ** 2) ** 0.5 / max(1e-6, time_s - last["t_s"]),
                                    3,
                                )
                                if last
                                else None
                            ),
                            "sample_interval_s": round(elapsed, 3),
                        }
                    )
            samples.append(sample)

        return {
            "provider": self.name,
            "model": "ffmpeg ppm + pure-python statistics",
            "demo_mode": True,
            "task": task,
            "frames_seen": len(stats),
            "grid": [GRID, GRID],
            "thresholds": {
                "bright_luma": BRIGHT_LUMA,
                "green_margin": GREEN_MARGIN,
                "motion_cell_delta": MOTION_CELL_THRESHOLD,
                "min_bright_fraction": MIN_BRIGHT_FRACTION,
                "min_centroid_shift": MIN_CENTROID_SHIFT,
            },
            "samples": samples,
            "events": events,
            "green_fraction_mean": round(sum(item.green_fraction for item in stats) / len(stats), 4),
            "limitations": (
                "This measures luminance and the movement of the centre of non-pitch pixels on a 96 px-wide copy of the "
                "clip. It does not detect players, a ball, formations or football events, and no number here is a claim "
                "about the game — a real vision model would replace this provider behind the same interface."
            ),
        }
