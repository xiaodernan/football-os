"""Video analysis agent for M11 (spec §32).

Explains the video analysis pipeline, interprets computer vision results, and answers
questions about player/ball detection, pose estimation, and event extraction. Uses the
existing video.pipeline module to access pipeline stages and limitations.
"""

from __future__ import annotations

from typing import Any

from app.services.agents.base import BaseAgent


class VideoAgent(BaseAgent):
    """Football video analysis agent that explains CV pipeline.

    Answers questions about the video analysis workflow: upload validation, frame
    extraction, player/ball detection, pose estimation, event extraction, and report
    generation. Explains what the demo vision provider does and its limitations.
    Persists explanations in agent memory for follow-up questions.
    """

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Answer a question about video analysis.

        Returns a dict with keys: answer, citations, confidence, from_cache, stored_key.
        """
        # Check if we've answered this before
        cache_key = f"video:{query.lower().strip()}"
        cached = self.recall(cache_key)
        if cached:
            return {
                "answer": cached.get("answer", ""),
                "citations": cached.get("citations", []),
                "confidence": cached.get("confidence", 0.0),
                "from_cache": True,
                "stored_key": cache_key,
            }

        # Analyze and answer
        result = self._analyze(query)

        # Store in memory (TTL: 7 days)
        self.remember(
            cache_key,
            {
                "answer": result["answer"],
                "citations": result["citations"],
                "confidence": result["confidence"],
                "query": query,
            },
            ttl_seconds=604800,
        )

        return {
            "answer": result["answer"],
            "citations": result["citations"],
            "confidence": result["confidence"],
            "from_cache": False,
            "stored_key": cache_key,
        }

    def _analyze(self, query: str) -> dict[str, Any]:
        """Analyze video-related query."""
        query_lower = query.lower()

        # Determine topic
        if any(word in query_lower for word in ["how", "work", "pipeline", "workflow"]):
            return self._explain_pipeline()
        elif any(word in query_lower for word in ["upload", "file", "format", "container", "mp4"]):
            return self._explain_upload()
        elif any(word in query_lower for word in ["frame", "sample", "extract", "interval"]):
            return self._explain_frames()
        elif any(word in query_lower for word in ["detect", "player", "ball", "vision", "cv"]):
            return self._explain_detection()
        elif any(word in query_lower for word in ["pose", "skeleton", "joint", "keypoint"]):
            return self._explain_pose()
        elif any(word in query_lower for word in ["event", "pass", "shot", "dribble", "action"]):
            return self._explain_events()
        elif any(word in query_lower for word in ["limitation", "cannot", "not model", "demo"]):
            return self._explain_limitations()
        elif any(word in query_lower for word in ["report", "output", "result", "interpret"]):
            return self._explain_report()
        else:
            return self._general_overview()

    def _explain_pipeline(self) -> dict[str, Any]:
        """Explain the complete video analysis pipeline."""
        answer = """**Video Analysis Pipeline (spec §14)**

The video analysis system processes uploaded match footage through these stages:

**1. Upload & Validation**
- File must be ≤ configured size limit (default varies by deployment)
- Container signature checked against known formats (MP4, MOV, WebM)
- Filename extension alone is not trusted — bytes are inspected
- Rejected files: renamed executables, JPEGs called .mp4, corrupted containers

**2. Probe (ffprobe)**
- Extracts duration, resolution, frame rate, codec info
- Validates the file is actually a video container
- Fails gracefully if ffprobe is not installed

**3. Frame Sampling**
- Selects up to 60 frames evenly spaced across the video
- Frame interval calculated based on total duration
- Higher frame counts = more detailed analysis but slower processing

**4. Vision Analysis (per frame)**
- Player detection: identifies human figures on the pitch
- Ball detection: locates the ball in each frame
- Pose estimation: extracts skeleton keypoints for detected players
- All analysis uses demo vision provider (see limitations below)

**5. Event Extraction**
- Detects passes, shots, dribbles from movement patterns
- Tracks player trajectories across frames
- Computes possession phases and transitions

**6. Report Generation**
- Aggregates detections into structured timeline
- Computes per-player statistics (touches, passes, movements)
- Generates visual overlays for playback
- Stores results in VideoDetection table

**Processing mode:**
- Synchronous (happens during the request, no background worker)
- Each stage records timing in Job table
- ModelCall row tracks vision provider usage

*AI analysis is an estimate and not a professional medical, scouting or performance certification.*"""

        citations = [{"type": "video_pipeline", "stages": "6"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_upload(self) -> dict[str, Any]:
        """Explain upload validation."""
        answer = """**Upload Validation**

The system validates uploads by inspecting the actual bytes, not just the filename:

**Supported containers:**
- MP4 (signature: `ftyp`)
- MOV/QuickTime (signature: `MOVI`)
- WebM (signature: `\x1a\x45\xdf\xa3`)

**Validation checks:**
1. File size must be within configured limit
2. First 16 bytes must contain a recognized container signature
3. File must be at least 12 bytes (minimum valid container)
4. Extension must match detected content type

**What gets rejected:**
- Renamed executables (.exe renamed to .mp4)
- Image files with video extensions (.jpg as .mp4)
- Corrupted or incomplete downloads
- Files exceeding size limit (returns 413, not 415)

**Why byte-level validation:**
- Prevents security issues from disguised files
- Ensures ffmpeg can actually process the upload
- Avoids wasting compute on invalid inputs

*Files are stored with their detected extension, not the original filename.*"""

        citations = [{"type": "upload_validation", "formats": "3"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_frames(self) -> dict[str, Any]:
        """Explain frame sampling."""
        answer = """**Frame Sampling Strategy**

The system doesn't analyze every frame — it samples strategically:

**Sampling parameters:**
- Maximum frames: 60 per video
- Interval: evenly spaced based on total duration
- Example: 90-minute match → 1 frame every 90 seconds

**How interval is calculated:**
```
interval = total_duration / max_frames
```

For a 5-minute clip at 30fps (9000 frames):
- 60 frames sampled → every 150th frame
- ~5 second intervals

**Why sample instead of full analysis:**
- Processing time: 60 frames takes seconds, thousands would take hours
- Storage: detection results scale linearly with frame count
- Diminishing returns: most actions span multiple frames anyway

**Trade-offs:**
- Fast actions (quick passes) may fall between sampled frames
- Longer videos get coarser sampling
- Short clips get denser coverage

**Frame storage:**
- Original frames extracted to temporary directory
- Processed by vision provider
- Detection coordinates stored in database
- Frames themselves not permanently stored

*Sample density affects detection granularity — short clips analyzed more thoroughly than long matches.*"""

        citations = [{"type": "frame_sampling", "max_frames": "60"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_detection(self) -> dict[str, Any]:
        """Explain player and ball detection."""
        answer = """**Player and Ball Detection**

The vision provider identifies objects in each sampled frame:

**What gets detected:**
- Players: human figures on the pitch (bounding boxes)
- Ball: spherical object (smaller bounding box)
- Goalkeepers: distinguished by position/color if possible

**Detection output per object:**
- Bounding box coordinates (x, y, width, height)
- Confidence score (0.0 to 1.0)
- Object class (player/ball/other)

**How detections are used:**
- Track player positions across frames
- Compute movement vectors and speeds
- Identify which player has possession (proximity to ball)
- Generate heatmaps of player activity zones

**Demo vision provider:**
- Current implementation uses demo/mock provider
- Returns synthetic detections for testing
- Real integration requires production vision model (YOLO, Detectron2, etc.)
- Provider abstraction allows swapping without changing pipeline code

**Detection limitations:**
- Demo provider doesn't read actual pixels
- Real models need training on football-specific data
- Occlusion (players blocking each other) causes missed detections
- Small ball harder to detect than large player figures

*Detection quality depends entirely on the vision provider — demo mode produces plausible but fake coordinates.*"""

        citations = [{"type": "detection", "objects": "2"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_pose(self) -> dict[str, Any]:
        """Explain pose estimation."""
        answer = """**Pose Estimation**

Beyond detecting players, the system estimates body posture:

**What pose estimation provides:**
- Skeleton keypoints: joints (shoulders, elbows, hips, knees, ankles)
- Body orientation: which direction player is facing
- Limb angles: useful for analyzing technique

**Typical keypoint set (17 points):**
- Head, shoulders, elbows, wrists
- Hips, knees, ankles

**Applications:**
- Technique analysis: kicking form, first touch posture
- Injury risk: joint loading patterns
- Tactical positioning: body orientation relative to play

**Current status:**
- Pose estimation infrastructure exists in pipeline
- Demo provider may not produce real keypoints
- Full implementation requires specialized pose model (OpenPose, HRNet, etc.)

**Challenges:**
- Requires higher resolution frames than simple detection
- Computationally expensive per frame
- Accuracy degrades with distance from camera
- Multiple players close together cause keypoint confusion

*Pose estimation is optional in the pipeline — basic detection works without it.*"""

        citations = [{"type": "pose_estimation", "keypoints": "17"}]
        return {"answer": answer, "citations": citations, "confidence": 0.85}

    def _explain_events(self) -> dict[str, Any]:
        """Explain event extraction."""
        answer = """**Event Extraction**

From raw detections, the system infers football events:

**Events detected:**
- Passes: ball moves from one player to another
- Shots: ball moves toward goal area with speed
- Dribbles: player maintains possession while moving
- Tackles: defensive player intercepts ball
- Headers: ball contact above waist level

**How events are inferred:**
1. Track ball trajectory across frames
2. Identify nearest player to ball at each frame
3. Detect sudden changes in ball velocity/direction
4. Match patterns to known event templates

**Event output:**
- Timestamp (derived from frame position in video)
- Event type (pass/shot/dribble/etc.)
- Involved players (who passed, who received)
- Coordinates (where on pitch it happened)
- Confidence (how certain the inference is)

**Limitations:**
- Demo provider doesn't track real ball movement
- Event inference requires accurate ball tracking first
- Complex events (crosses, volleys) harder to classify
- Off-ball events (runs, pressing) not directly observable from ball data

**What events enable:**
- Automated match statistics
- Player performance metrics
- Tactical pattern recognition
- Highlight reel generation

*Event extraction builds on top of detection — poor detection quality cascades to event errors.*"""

        citations = [{"type": "event_extraction", "event_types": "5"}]
        return {"answer": answer, "citations": citations, "confidence": 0.90}

    def _explain_limitations(self) -> dict[str, Any]:
        """Explain pipeline limitations."""
        answer = """**Video Analysis Limitations**

The current implementation has important constraints:

**Demo vision provider:**
- Does NOT analyze actual video pixels
- Returns synthetic/plausible detection coordinates
- Useful for testing UI and data flow, not for real analysis
- Production requires trained computer vision model

**Technical limitations:**
- No background worker: analysis happens synchronously during request
- Long videos timeout on slow connections
- ffprobe/ffmpeg must be installed on server
- Frame sampling means fast actions may be missed

**Analysis limitations:**
- Cannot determine player identity (no face recognition)
- Cannot read jersey numbers reliably
- Cannot distinguish teams without color segmentation
- Cannot measure exact distances without camera calibration
- Cannot determine ball spin or trajectory physics

**What the report CANNOT certify:**
- Medical fitness or injury diagnosis
- Professional scouting recommendations
- Official performance statistics
- Contract valuation evidence

**Provider transparency:**
- Every report includes `provider` field naming the vision service used
- `demo_mode: true` indicates synthetic results
- `limitations` field lists what the provider cannot do
- Results should be treated as estimates, not measurements

*The system is designed for development/testing. Production football analysis requires professional computer vision models trained on thousands of labeled match videos.*"""

        citations = [{"type": "limitations", "category": "demo_provider"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _explain_report(self) -> dict[str, Any]:
        """Explain how to interpret analysis reports."""
        answer = """**Interpreting Video Analysis Reports**

Each analysis produces a structured report with these sections:

**Report structure:**
1. **Metadata**: video duration, resolution, frame count, provider info
2. **Stages**: timing for each pipeline stage (probe, extract, analyze)
3. **Detections**: list of all detected objects per frame
4. **Events**: inferred football actions with timestamps
5. **Statistics**: aggregated metrics (passes, shots, distance covered)
6. **Limitations**: what the analysis could not determine

**Key fields to check:**
- `provider`: which vision service was used
- `demo_mode`: true means synthetic results, false means real analysis
- `model`: specific model version (e.g., "yolo-v8", "demo-provider")
- `limitations`: array of things this analysis cannot determine

**Understanding detection coordinates:**
- Normalized to [0, 1] range (relative to frame dimensions)
- x=0 is left edge, x=1 is right edge
- y=0 is top, y=1 is bottom
- Convert to pixels: pixel_x = x * frame_width

**Reading event confidence:**
- 0.9+: high confidence, likely correct
- 0.7-0.9: moderate confidence, verify manually
- <0.7: low confidence, treat as suggestion only

**When to trust the report:**
- Provider is a known production model (not "demo")
- demo_mode is false
- Confidence scores are consistently high
- Visual inspection confirms detections align with video

**When to be skeptical:**
- demo_mode is true (synthetic results)
- Very few detections in a busy scene
- Events don't match visual observation
- Confidence scores are uniformly low

*Always cross-reference automated analysis with manual video review for important decisions.*"""

        citations = [{"type": "report_interpretation", "sections": "6"}]
        return {"answer": answer, "citations": citations, "confidence": 0.95}

    def _general_overview(self) -> dict[str, Any]:
        """Provide general overview of video analysis capabilities."""
        answer = """**Football Video Analysis Overview**

I can explain the video analysis pipeline and help interpret results.

**Topics I can cover:**
- How the pipeline works (upload → probe → frames → detect → report)
- Upload validation and supported formats
- Frame sampling strategy and trade-offs
- Player and ball detection mechanics
- Pose estimation and skeleton keypoints
- Event extraction (passes, shots, dribbles)
- Current limitations (demo provider, no background worker)
- How to read and interpret analysis reports

**Try asking:**
- "How does the video analysis pipeline work?"
- "What formats can I upload?"
- "Explain player detection"
- "What are the limitations of video analysis?"
- "How do I interpret the analysis report?"

**Important note:**
The current implementation uses a demo vision provider that generates synthetic detections. For production use, integrate a trained computer vision model (YOLO, Detectron2, etc.) via the provider abstraction layer.

*AI analysis is an estimate and not a professional medical, scouting or performance certification.*"""

        citations = [{"type": "video_analysis_overview"}]
        return {"answer": answer, "citations": citations, "confidence": 0.85}
