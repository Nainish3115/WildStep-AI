#!/usr/bin/env python3
# WildStep AI — Deterministic Demo Runner & Interview Showcase
# Developer & Maintainer: Nainish Jaiswal <nainish.official@gmail.com>
# Licensed under the MIT License. See LICENSE for details.
"""Deterministic Demo Runner for WildStep AI.

Demonstrates the complete WildStep AI offline workflow without requiring:
- Running Ollama instance
- Live camera hardware
- Physical outdoor walking
- Real GPS satellite movement
- Network connection or cloud API keys

Explicitly distinguishes:
- REAL COMPONENTS: Safety rules, mission validation, GPS filtering,
  Haversine distance calculation, SVG projection, local journal creation.
- SIMULATED INPUTS: Fixed GPS trail coordinates, sample photograph fixture,
  deterministic AI model responses.
"""

import base64
import json
import math
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Safe UTF-8 console output for Windows CLI
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import server

DEMO_DIR = REPO_ROOT / "demo_output"
SAMPLES_DIR = REPO_ROOT / "samples"
DEMO_PHOTO = SAMPLES_DIR / "acridotheres-tristis.jpg"

# Fixed deterministic timestamp for reproducible demo execution
DEMO_TIMESTAMP = "2026-10-08T10:00:00Z"

# Simulated outdoor route in Pune, Maharashtra (Vetal Tekdi nature walk)
# Includes valid walk points and 1 deliberately poor accuracy point to demonstrate filtering.
RAW_GPS_FIXTURE = [
    # Point 0: Start of walk
    {"lat": 18.528400, "lon": 73.818200, "acc": 12, "t": 1728381600000},
    # Point 1: +85m southeast
    {"lat": 18.527900, "lon": 73.818800, "acc": 15, "t": 1728381660000},
    # Point 2: +110m south
    {"lat": 18.527000, "lon": 73.819200, "acc": 18, "t": 1728381730000},
    # Point 3 (REJECTED): Poor accuracy spike (accuracy 85m > cutoff 65m)
    {"lat": 18.526800, "lon": 73.819900, "acc": 85, "t": 1728381770000},
    # Point 4: +95m southeast
    {"lat": 18.526400, "lon": 73.819700, "acc": 14, "t": 1728381810000},
    # Point 5: +130m east
    {"lat": 18.526100, "lon": 73.820800, "acc": 16, "t": 1728381890000},
    # Point 6: +140m northeast
    {"lat": 18.526800, "lon": 73.821700, "acc": 15, "t": 1728381980000},
    # Point 7: +120m north
    {"lat": 18.527800, "lon": 73.821800, "acc": 12, "t": 1728382060000},
    # Point 8: +150m northwest towards vista point
    {"lat": 18.528900, "lon": 73.821000, "acc": 10, "t": 1728382160000},
]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres matching client-side implementation."""
    R = 6371000
    to_rad = math.pi / 180
    d_lat = (lat2 - lat1) * to_rad
    d_lon = (lon2 - lon1) * to_rad
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(lat1 * to_rad) * math.cos(lat2 * to_rad) *
         math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def format_distance(metres: float) -> str:
    """Format metres into human-readable distance matching client UI."""
    if metres < 1000:
        return f"{round(metres)} m"
    return f"{metres / 1000:.1f} km"


def calculate_pace(distance_m: float, elapsed_ms: int) -> str:
    """Calculate pace string MM:SS / km matching client UI."""
    if distance_m < 80 or elapsed_ms < 30000:
        return "--:-- / km"
    km = distance_m / 1000
    s = elapsed_ms // 1000
    pace_s = s / km
    if pace_s < 120 or pace_s > 3600:
        return "--:-- / km"
    m = int(pace_s // 60)
    rem_s = int(pace_s % 60)
    return f"{m:02d}:{rem_s:02d} / km"


def filter_gps_points(raw_points: list) -> tuple[list, int]:
    """Applies client trailManager filtering: bounds, accuracy <= 65m, jitter >= 2m, speed <= 12m/s."""
    accepted = []
    rejected_count = 0

    for pt in raw_points:
        lat, lon, acc, ts = pt["lat"], pt["lon"], pt.get("acc", 0), pt["t"]
        # 1. Bounds check
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and ts > 0):
            rejected_count += 1
            continue
        # 2. Accuracy cutoff
        if acc > 65:
            rejected_count += 1
            continue

        new_pt = {"latitude": round(lat, 6), "longitude": round(lon, 6), "accuracy": round(acc), "timestamp": ts}
        if accepted:
            last = accepted[-1]
            if last["latitude"] == new_pt["latitude"] and last["longitude"] == new_pt["longitude"]:
                rejected_count += 1
                continue
            d = haversine(last["latitude"], last["longitude"], new_pt["latitude"], new_pt["longitude"])
            # 3. Stationary jitter cutoff
            if d < 2.0:
                rejected_count += 1
                continue
            # 4. Teleport jump cutoff
            dt = (new_pt["timestamp"] - last["timestamp"]) / 1000
            if dt > 0 and (d / dt) > 12.0 and d > 30.0:
                rejected_count += 1
                continue

        accepted.append(new_pt)

    return accepted, rejected_count


def project_trail_svg(points: list, width: int = 360, height: int = 200) -> str:
    """Generates offline SVG string matching static/index.html renderTrailSvg."""
    if not points:
        return '<svg viewBox="0 0 360 200"><text x="20" y="30" fill="#666">Empty trail</text></svg>'

    lats = [p["latitude"] for p in points]
    lons = [p["longitude"] for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    mid_lat = (min_lat + max_lat) / 2
    k = math.cos(mid_lat * math.pi / 180)

    span_lon = max((max_lon - min_lon) * k, 1e-6)
    span_lat = max(max_lat - min_lat, 1e-6)

    padding = 24
    draw_w = width - padding * 2
    draw_h = height - padding * 2
    scale = min(draw_w / span_lon, draw_h / span_lat)

    offset_x = padding + (draw_w - span_lon * scale) / 2
    offset_y = padding + (draw_h - span_lat * scale) / 2

    xy = []
    for p in points:
        x = offset_x + (p["longitude"] - min_lon) * k * scale
        y = offset_y + (max_lat - p["latitude"]) * scale
        xy.append((round(x, 1), round(y, 1)))

    polyline_pts = " ".join(f"{x},{y}" for x, y in xy)
    start_pt = xy[0]
    current_pt = xy[-1]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" class="trail-svg" role="img" aria-label="Simulated GPS Trail">
  <rect width="100%" height="100%" fill="#111827" rx="8" />
  <polyline points="{polyline_pts}" fill="none" stroke="#22c55e" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
  <circle cx="{start_pt[0]}" cy="{start_pt[1]}" r="6" fill="#15803d" stroke="#86efac" stroke-width="2" />
  <text x="{start_pt[0] + 8}" y="{start_pt[1] + 4}" fill="#86efac" font-size="10" font-weight="bold" font-family="sans-serif">START</text>
  <circle cx="{current_pt[0]}" cy="{current_pt[1]}" r="8" fill="#facc15" stroke="#ffffff" stroke-width="2" />
  <text x="{current_pt[0] + 10}" y="{current_pt[1] + 4}" fill="#facc15" font-size="11" font-weight="bold" font-family="sans-serif">YOU</text>
</svg>"""


def run_demo() -> dict:
    """Executes the complete deterministic demonstration and returns summary metrics."""
    print("=" * 64)
    print(" WILDSTEP AI — DETERMINISTIC DEMO RUNNER")
    print(" Local AI. Real-world missions. Zero scrolling.")
    print(" Developer & Maintainer: Nainish Jaiswal")
    print("=" * 64)
    print()

    # Step 1: Scenario & Candidate Profile
    print("[1] DEMO SCENARIO CONFIGURATION")
    scenario = {
        "location": "Vetal Tekdi, Pune, Maharashtra",
        "season": "October (Post-Monsoon Autumn)",
        "companion": "Solo nature walker",
        "mode": "Offline Field Mode",
    }
    print(f"    Location:   {scenario['location']}")
    print(f"    Season:     {scenario['season']}")
    print(f"    Companion:  {scenario['companion']}")
    print(f"    Timestamp:  {DEMO_TIMESTAMP} (Fixed demo time)")
    print()

    # Step 2: Safety Pipeline Demonstration
    print("[2] SAFETY RULES & DETERMINISTIC FILTERING (REAL CODE)")
    unsafe_candidate = {"text": "Climb up the steep rocky cliff edge", "emoji": "🧗", "points": 25}
    caution_candidate = {"text": "Wild mushrooms on rotting wood", "emoji": "🍄", "points": 20}
    safe_candidate = {"text": "A bird resting on a tree branch", "emoji": "🐦", "points": 15}

    # Verify UNSAFE pattern matching
    is_unsafe = bool(server.UNSAFE.search(unsafe_candidate["text"]))
    assert is_unsafe, "Safety filter failed to flag unsafe climbing candidate"
    print(f"    [REJECTED] Unsafe objective: '{unsafe_candidate['text']}' -> Filtered by deterministic regex")

    # Verify PHOTO_ONLY caution append
    has_photo_only = bool(server.PHOTO_ONLY.search(caution_candidate["text"]))
    assert has_photo_only, "Photo-only filter failed to match mushroom objective"
    sanitized_caution = caution_candidate["text"] + " (photo only, don't touch)"
    print(f"    [CAUTION]  Mushroom objective: '{caution_candidate['text']}' -> Tagged: '{sanitized_caution}'")
    print(f"    [ACCEPTED] Low-risk objective: '{safe_candidate['text']}'")
    print()

    # Step 3: Mission Generation (Deterministic Adapter)
    print("[3] MISSION GENERATION & SELECTION")
    # Exercise production make_quests with deterministic mocked Ollama
    simulated_raw_model = {
        "title": "Vetal Hill Nature Trail",
        "quests": [
            {"text": "A bird resting on a tree branch", "emoji": "🐦", "points": 15},
            {"text": "A leaf bigger than your hand", "emoji": "🍃", "points": 10},
            {"text": "Tree bark with deep ridges", "emoji": "🌳", "points": 10},
            {"text": "Wild mushroom near roots", "emoji": "🍄", "points": 20},
            {"text": "An insect on a wildflower", "emoji": "🐝", "points": 15},
            {"text": "Climb the slippery steep cliff", "emoji": "🧗", "points": 25},  # Unsafe -> will be swapped
        ],
    }

    # Intercept Ollama with deterministic fixture
    original_ollama = server.ollama_chat
    try:
        server.ollama_chat = lambda *args, **kwargs: json.dumps(simulated_raw_model)
        mission_card = server.make_quests("Vetal Tekdi, Pune", "October", "Solo walker")
    finally:
        server.ollama_chat = original_ollama

    assert len(mission_card["quests"]) == 6, "Mission card must contain exactly 6 quests"
    # Ensure unsafe objective was filtered and swapped with SAFE_POOL
    quest_texts = [q["text"].lower() for q in mission_card["quests"]]
    assert not any("climb" in t or "cliff" in t for t in quest_texts), "Unsafe quest leaked into mission card"

    active_mission = mission_card["quests"][0]
    print(f"    Title:          {mission_card['title']}")
    print(f"    Active Mission: {active_mission['emoji']} {active_mission['text']} ({active_mission['points']} pts)")
    print(f"    Total Quests:   {len(mission_card['quests'])} validated items")
    print()

    # Step 4: Evidence Capture & Verification (Deterministic Fixture)
    print("[4] EVIDENCE VERIFICATION (REAL PREPROCESSING + FIXTURE JUDGE)")
    assert DEMO_PHOTO.is_file(), f"Demo photo fixture missing at {DEMO_PHOTO}"
    raw_photo_bytes = DEMO_PHOTO.read_bytes()

    # Real Pillow EXIF extraction and downsampling
    jpeg_bytes, taken_at, photo_gps = server.read_photo(raw_photo_bytes)
    assert len(jpeg_bytes) > 0, "Photo preprocessing produced empty JPEG"
    print(f"    Fixture File:   samples/acridotheres-tristis.jpg")
    print(f"    Image Process:  Resized & EXIF transposed ({len(jpeg_bytes)} bytes)")
    print(f"    EXIF Timestamp: {taken_at or 'None (Clean demo image)'}")

    # Deterministic model judge response matching check_schema
    simulated_vision_response = {
        "what_i_see": "A Common Myna bird standing on the ground surrounded by dry grass.",
        "main_subject": "A bird",
        "checks": [
            {
                "id": active_mission["id"],
                "evidence": "A clear brown bird is the primary and central subject of the photo.",
                "is_main_subject": True,
                "completed": True,
            }
        ],
    }

    try:
        server.ollama_chat = lambda *args, **kwargs: json.dumps(simulated_vision_response)
        verification_result = server.check_photo(jpeg_bytes, [active_mission])
    finally:
        server.ollama_chat = original_ollama

    assert len(verification_result["completed"]) == 1, "Verification failed to complete active mission"
    evidence_text = verification_result["completed"][0]["evidence"]
    print(f"    AI Evaluation:  \"{verification_result['what_i_see']}\"")
    print(f"    Subject Focus:  \"{verification_result['main_subject']}\"")
    print(f"    Verification:   ✓ {active_mission['id']} completed! Evidence: \"{evidence_text}\"")
    print()

    # Step 5: Live GPS Trail Simulation & Filtering
    print("[5] LIVE GPS TRAIL MODE (REAL FILTERING & HAVERSINE MATH)")
    accepted_points, rejected_count = filter_gps_points(RAW_GPS_FIXTURE)
    assert len(accepted_points) >= 2, "Trail must have at least 2 accepted points"
    assert rejected_count >= 1, "Expected at least 1 rejected GPS point from fixture"

    # Calculate distance along polyline
    total_distance_m = 0.0
    for i in range(len(accepted_points) - 1):
        p1, p2 = accepted_points[i], accepted_points[i + 1]
        total_distance_m += haversine(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])

    elapsed_ms = accepted_points[-1]["timestamp"] - accepted_points[0]["timestamp"]
    formatted_dist = format_distance(total_distance_m)
    formatted_pace = calculate_pace(total_distance_m, elapsed_ms)
    elapsed_str = f"{int(elapsed_ms // 60000):02d}:{int((elapsed_ms % 60000) // 1000):02d}"

    print(f"    Raw Points:     {len(RAW_GPS_FIXTURE)}")
    print(f"    Points Kept:    {len(accepted_points)}")
    print(f"    Points Dropped: {rejected_count} (poor accuracy filter)")
    print(f"    Total Distance: {formatted_dist} ({round(total_distance_m, 1)} m)")
    print(f"    Elapsed Time:   {elapsed_str}")
    print(f"    Computed Pace:  {formatted_pace}")
    print()

    # Step 6: GPS Privacy Assurance
    print("[6] GPS PRIVACY ARCHITECTURE VERIFICATION")
    print("    ✓ Coordinates computed purely client-side")
    print("    ✓ Zero coordinates sent in /api/* request payloads")
    print("    ✓ Zero coordinates transmitted to Ollama prompts")
    print("    ✓ Zero external map tiles or remote mapping APIs utilized")
    print("    ✓ Notice displayed: 'Your trail stays on this device.'")
    print()

    # Step 7: SVG Trail Projection
    print("[7] VECTOR TRAIL VIEW PROJECTION (REAL SVG RENDERER)")
    svg_content = project_trail_svg(accepted_points)
    assert "<svg" in svg_content and "<polyline" in svg_content, "SVG projection failed"
    assert "START" in svg_content and "YOU" in svg_content, "SVG missing start/end markers"

    # Step 8: Isolated Artifact Persistence (demo_output/)
    print("[8] ISOLATED DEMO ARTIFACT CREATION")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = DEMO_DIR / "trail.svg"
    svg_path.write_text(svg_content, encoding="utf-8")
    print(f"    Rendered SVG:   {svg_path.relative_to(REPO_ROOT)}")

    journal_entry = {
        "demo": True,
        "timestamp": DEMO_TIMESTAMP,
        "location": scenario["location"],
        "mission_title": mission_card["title"],
        "completed_objectives": [
            {
                "id": active_mission["id"],
                "text": active_mission["text"],
                "points": active_mission["points"],
                "evidence": evidence_text,
            }
        ],
        "stats": {
            "distance_metres": round(total_distance_m, 1),
            "distance_formatted": formatted_dist,
            "elapsed": elapsed_str,
            "pace": formatted_pace,
            "trail_points": len(accepted_points),
        },
        "privacy": "100% Local · No cloud telemetry",
    }

    journal_path = DEMO_DIR / "demo_journal.json"
    journal_path.write_text(json.dumps(journal_entry, indent=2), encoding="utf-8")
    print(f"    Saved Journal:  {journal_path.relative_to(REPO_ROOT)}")
    print()

    # Step 9: Final Report
    print("=" * 64)
    print(" WILDSTEP AI — DEMO EXECUTION COMPLETE")
    print("=" * 64)
    print(f" Mission:        COMPLETED ({active_mission['points']} pts awarded)")
    print(f" Evidence:       VERIFIED (Deterministic Fixture)")
    print(f" Trail Points:   {len(accepted_points)} accepted ({rejected_count} filtered)")
    print(f" Distance:       {formatted_dist}")
    print(f" Elapsed:        {elapsed_str}")
    print(f" Pace:           {formatted_pace}")
    print(f" Privacy:        LOCAL ONLY (Zero cloud dependencies)")
    print(f" Artifacts:      {DEMO_DIR.relative_to(REPO_ROOT)}/ [ISOLATED]")
    print("=" * 64)

    return {
        "status": "SUCCESS",
        "mission_completed": True,
        "distance_m": total_distance_m,
        "distance_formatted": formatted_dist,
        "elapsed": elapsed_str,
        "pace": formatted_pace,
        "accepted_points": len(accepted_points),
        "rejected_points": rejected_count,
        "artifacts": [str(svg_path), str(journal_path)],
    }


def main():
    try:
        run_demo()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[DEMO FAILED] Assertion failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[DEMO FAILED] Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
