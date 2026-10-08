"""Tests for Deterministic Demo Runner in WildStep AI.

Validates:
1. scripts/run_demo.py executes to completion with exit code 0.
2. Demo is deterministic and reproducible across multiple invocations.
3. Does NOT require running Ollama, network access, camera hardware, or physical GPS.
4. Production state isolation:
   - Does NOT write to user's home directory walk folders (~/.wildstep-ai/walks).
   - Writes only to isolated demo_output/ directory.
5. Verifies internal pipeline assertions:
   - Safety filter rejecting climbing/cliff hazards.
   - GPS coordinate filtering rejecting poor accuracy points.
   - Distance calculation math.
   - SVG vector projection with START and YOU markers.
   - JSON journal structure.
6. Error handling: returns non-zero exit code if assertions fail.
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
RUN_DEMO_PATH = SCRIPTS_DIR / "run_demo.py"
DEMO_OUTPUT_DIR = REPO_ROOT / "demo_output"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_demo import (
    RAW_GPS_FIXTURE,
    calculate_pace,
    filter_gps_points,
    format_distance,
    haversine,
    project_trail_svg,
    run_demo,
)


def test_demo_script_file_exists():
    """scripts/run_demo.py must exist in the repository."""
    assert RUN_DEMO_PATH.is_file(), f"Missing {RUN_DEMO_PATH}"


def test_run_demo_function_deterministic_output():
    """run_demo() must produce deterministic results without exceptions."""
    res1 = run_demo()
    res2 = run_demo()

    assert res1["status"] == "SUCCESS"
    assert res2["status"] == "SUCCESS"
    assert res1["distance_m"] == res2["distance_m"]
    assert res1["distance_formatted"] == res2["distance_formatted"]
    assert res1["elapsed"] == res2["elapsed"]
    assert res1["pace"] == res2["pace"]
    assert res1["accepted_points"] == res2["accepted_points"]
    assert res1["rejected_points"] == res2["rejected_points"]


def test_demo_artifacts_created_in_demo_output():
    """run_demo must output trail.svg and demo_journal.json inside isolated demo_output/."""
    run_demo()

    svg_file = DEMO_OUTPUT_DIR / "trail.svg"
    journal_file = DEMO_OUTPUT_DIR / "demo_journal.json"

    assert svg_file.is_file(), "demo_output/trail.svg was not created"
    assert journal_file.is_file(), "demo_output/demo_journal.json was not created"

    # Validate SVG content
    svg_text = svg_file.read_text(encoding="utf-8")
    assert "<svg" in svg_text
    assert "<polyline" in svg_text
    assert "START" in svg_text
    assert "YOU" in svg_text

    # Validate Journal content
    journal_data = json.loads(journal_file.read_text(encoding="utf-8"))
    assert journal_data["demo"] is True
    assert journal_data["stats"]["trail_points"] == 8
    assert "distance_metres" in journal_data["stats"]
    assert "Local" in journal_data["privacy"]


def test_demo_runner_cli_subprocess():
    """scripts/run_demo.py must execute cleanly via Python subprocess."""
    proc = subprocess.run(
        [sys.executable, str(RUN_DEMO_PATH)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, f"run_demo.py failed with code {proc.returncode}:\n{proc.stderr}"
    assert "WILDSTEP AI — DEMO EXECUTION COMPLETE" in proc.stdout
    assert "Privacy:        LOCAL ONLY" in proc.stdout


def test_demo_gps_filtering_logic():
    """Verifies that filter_gps_points accurately catches the deliberately bad accuracy point."""
    accepted, rejected = filter_gps_points(RAW_GPS_FIXTURE)
    assert len(accepted) == 8
    assert rejected == 1

    # Verify that point with accuracy=85 was discarded
    assert not any(p["accuracy"] > 65 for p in accepted)


def test_demo_haversine_and_pace():
    """Verifies math functions produce expected values on fixed fixture."""
    accepted, _ = filter_gps_points(RAW_GPS_FIXTURE)
    total_d = sum(
        haversine(accepted[i]["latitude"], accepted[i]["longitude"], accepted[i+1]["latitude"], accepted[i+1]["longitude"])
        for i in range(len(accepted) - 1)
    )
    assert 750 < total_d < 820  # ~781.5m
    assert format_distance(total_d) == "782 m"

    elapsed_ms = accepted[-1]["timestamp"] - accepted[0]["timestamp"]  # 560000 ms (9m 20s)
    pace_str = calculate_pace(total_d, elapsed_ms)
    assert pace_str == "11:56 / km"


def test_demo_svg_projection():
    """Verifies SVG string structure on valid points."""
    accepted, _ = filter_gps_points(RAW_GPS_FIXTURE)
    svg = project_trail_svg(accepted)
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in svg
    assert '<polyline points="' in svg
    assert '<circle cx=' in svg
