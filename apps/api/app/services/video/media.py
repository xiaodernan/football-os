"""Media tools: what ffprobe reports and what ffmpeg extracts (spec §14, §47, §77).

`ffmpeg`/`ffprobe` are called as subprocesses with fixed argument lists — no shell string, so a
filename can never become a command. If either binary is absent the caller gets
`MediaToolMissing`, which the pipeline records as a job failure: the honest alternative to
inventing durations and frames is to say the tool is not installed.

Frames come out as binary PPM (P6): a header plus raw RGB bytes. That keeps the pixel analysis in
`vision.py` dependency-free, and it is why extraction downscales to a known width — the numbers a
user sees are quantised onto that grid, and the method says so out loud rather than implying
frame-perfect measurement.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

__all__ = ["FRAME_WIDTH", "Frame", "MediaInfo", "MediaToolMissing", "extract_frames", "ffprobe_path", "ffmpeg_path", "probe"]

FRAME_WIDTH: Final = 96
"""Analysis resolution. Width in px; height keeps the source aspect ratio."""

MAX_DURATION_SECONDS: Final = 900.0
MIN_PIXEL_ROWS: Final = 24


class MediaToolMissing(RuntimeError):
    """No ffmpeg/ffprobe on this host — video analysis cannot run, and must not pretend to."""


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


@dataclass(frozen=True)
class MediaInfo:
    """What the container says about the file, plus the two numbers the pipeline needs."""

    duration_s: float
    width: int
    height: int
    fps: float
    codec: str
    size_bytes: int
    bitrate_kbps: float
    probe_command: str = field(default="", repr=False)

    @property
    def aspect(self) -> float:
        return round(self.width / self.height, 4) if self.height else 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["aspect"] = self.aspect
        return payload


def _run(args: list[str]) -> str:
    executable = args[0]
    if shutil.which(executable) is None:
        raise MediaToolMissing(f"{executable} is not installed on this host")
    completed = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
    if completed.returncode != 0:
        raise ValueError(f"{executable} failed: {completed.stderr.strip()[:400] or completed.stdout.strip()[:200]}")
    return completed.stdout


def probe(path: Path) -> MediaInfo:
    """`ffprobe -print_format json` over the first video stream."""
    if ffprobe_path() is None:
        raise MediaToolMissing("ffprobe is not installed on this host")
    args = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,codec_name,duration,bit_rate:format=duration,size,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    payload = json.loads(_run(args))
    stream = (payload.get("streams") or [{}])[0]
    format_info = payload.get("format") or {}

    def as_float(*values: Any) -> float:
        for value in values:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return 0.0

    duration = as_float(stream.get("duration"), format_info.get("duration"))
    rate = str(stream.get("r_frame_rate") or "0/1")
    fps = 0.0
    if "/" in rate:
        numerator, _, denominator = rate.partition("/")
        fps = as_float(_safe_divide(numerator, denominator))
    size = path.stat().st_size if path.exists() else 0
    bitrate = as_float(stream.get("bit_rate"), format_info.get("bit_rate")) / 1000.0
    if not bitrate and duration and size:
        bitrate = size * 8 / 1000.0 / duration
    return MediaInfo(
        duration_s=round(duration, 3),
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        fps=round(fps, 3),
        codec=str(stream.get("codec_name") or "unknown"),
        size_bytes=int(size),
        bitrate_kbps=round(bitrate, 1),
        probe_command=" ".join(args[:-1]),
    )


def _safe_divide(numerator: str, denominator: str) -> float:
    try:
        top, bottom = float(numerator or 0), float(denominator or 0)
    except ValueError:
        return 0.0
    return top / bottom if bottom else 0.0


@dataclass(frozen=True)
class Frame:
    """One extracted sample: its file, its ordinal, and the time it stands for."""

    path: Path
    index: int
    time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "time_s": self.time_s, "file": self.path.name}


def to_png(ppm_path: Path) -> Path:
    """One extracted frame as PNG, because a browser cannot show a PPM.

    The analysis path deliberately reads the PPM: the measurement input stays the raw sample, and
    the encoded copy exists only for display. The PNG is written next to the frame once and reused.
    """
    png = ppm_path.with_suffix(".png")
    if png.exists() and png.stat().st_size > 0:
        return png
    if ffmpeg_path() is None:
        raise MediaToolMissing("ffmpeg is not installed on this host")
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(ppm_path), str(png)])
    return png


def frame_interval(duration_s: float, *, target_frames: int = 24) -> float:
    """Sample the clip evenly, but never finer than 0.25 s or coarser than the clip itself."""
    if duration_s <= 0:
        return 1.0
    raw = duration_s / max(2, target_frames)
    return min(max(raw, 0.25), max(duration_s, 0.5))


def extract_frames(path: Path, out_dir: Path, *, interval_s: float, max_frames: int = 60) -> list[Frame]:
    """Pull one frame every `interval_s` seconds into `out_dir` as PPM, smallest width first.

    Frame *n* is the first frame at or after ``n × interval_s`` — the timestamp is a sample point,
    not a measurement of when something happened.
    """
    if ffmpeg_path() is None:
        raise MediaToolMissing("ffmpeg is not installed on this host")
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame-%04d.ppm"
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-vf",
        f"fps={1.0 / interval_s:.6f},scale={FRAME_WIDTH}:-2:flags=area",
        "-pix_fmt",
        "rgb24",
        "-c:v",
        "ppm",
        "-frames:v",
        str(max_frames),
        "-y",
        str(pattern),
    ]
    _run(args)
    files = sorted(out_dir.glob("frame-*.ppm"))
    return [Frame(path=file, index=index, time_s=round(index * interval_s, 3)) for index, file in enumerate(files)]
