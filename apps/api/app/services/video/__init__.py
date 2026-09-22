"""Video analysis services (spec §14, §47).

Layering, and one import rule: `providers` imports `vision` to name the active vision provider, so
this package's root must not import `pipeline` (which imports `providers`) — that would be a cycle.
`pipeline` is therefore reached as a submodule (`from app.services.video import pipeline`) or by
importing it directly, exactly as the routes do.

``media``      ffprobe facts and ffmpeg frame samples, as subprocesses with fixed arguments
``vision``     PPM decoding plus the demo provider that measures the pixels
``pipeline``   upload validation, stage recording, detections, and the report
"""

from app.services.video.media import Frame, MediaInfo, MediaToolMissing, extract_frames, frame_interval, probe
from app.services.video.vision import DemoVisionProvider, GridStats, frame_stats, motion_between, read_ppm

__all__ = [
    "DemoVisionProvider",
    "Frame",
    "GridStats",
    "MediaInfo",
    "MediaToolMissing",
    "extract_frames",
    "frame_interval",
    "frame_stats",
    "motion_between",
    "probe",
    "read_ppm",
]
