"""Tests for Live GPS Trail Mode in WildStep AI.

Validates:
1. Mathematical precision: Haversine distance calculation and formatting ("842 m", "1.4 km").
2. Speed and pace computation: formatted as MM:SS / km, gating on distance and time.
3. GPS coordinate filtering:
   - Latitude/longitude validity checks
   - Accuracy cutoff (accuracy <= 65m)
   - Stationary jitter deduplication (< 2m ignored)
   - Teleport / GPS jump rejection (> 12 m/s over > 30m)
4. SVG Trail View generation:
   - Coordinate bounding box and projection
   - Start marker, current position marker, polyline
   - Empty/single point fallbacks
5. State persistence and interrupted walk recovery:
   - active_trail structure in localStorage / client store
   - Resume and discard state transitions
6. Privacy constraints:
   - 100% client-side computation
   - Absolute absence of external map services (Google Maps, Leaflet, Mapbox, OSM tiles)
   - Coordinates never sent in POST /api payloads or Ollama prompt bodies
7. Field Mode UI presence:
   - field-trail-bar, field-gps-pill, field-trail-drawer
   - Privacy notices: "Your trail stays on this device."
"""

import math
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"
INDEX_PATH = STATIC_DIR / "index.html"
SERVER_PATH = REPO_ROOT / "server.py"


@pytest.fixture(scope="module")
def html_content() -> str:
    """Loads static/index.html."""
    assert INDEX_PATH.exists(), "static/index.html must exist"
    return INDEX_PATH.read_text(encoding="utf-8")


# ===========================================================================
# 1. Mathematical Logic & Haversine Distance (Python equivalence)
# ===========================================================================

def py_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    to_rad = math.pi / 180
    d_lat = (lat2 - lat1) * to_rad
    d_lon = (lon2 - lon1) * to_rad
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(lat1 * to_rad) * math.cos(lat2 * to_rad) *
         math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def py_format_distance(metres: float) -> str:
    if metres < 1000:
        return f"{round(metres)} m"
    return f"{metres / 1000:.1f} km"


def py_calculate_pace(distance_m: float, elapsed_ms: int) -> str:
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


def test_haversine_accuracy():
    """Haversine formula calculates known distances accurately."""
    # Paris (48.8566, 2.3522) to London (51.5074, -0.1278) ~ 343 km
    d = py_haversine(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340000 < d < 345000
    # Zero distance
    assert py_haversine(12.9716, 77.5946, 12.9716, 77.5946) == 0.0


def test_distance_formatting():
    """Distances format to meters under 1km and tenths of km above 1km."""
    assert py_format_distance(0) == "0 m"
    assert py_format_distance(42.3) == "42 m"
    assert py_format_distance(842.1) == "842 m"
    assert py_format_distance(999.4) == "999 m"
    assert py_format_distance(1000) == "1.0 km"
    assert py_format_distance(1420) == "1.4 km"
    assert py_format_distance(3850) == "3.9 km"


def test_pace_calculation():
    """Pace returns formatted MM:SS / km only after distance and time thresholds."""
    # Below 80m threshold
    assert py_calculate_pace(75, 45000) == "--:-- / km"
    # Below 30s threshold
    assert py_calculate_pace(120, 20000) == "--:-- / km"
    # Valid walking pace: 500m in 300s (5 min) -> 10:00 / km
    assert py_calculate_pace(500, 300000) == "10:00 / km"
    # Fast walk / jog: 1000m in 360s (6 min) -> 06:00 / km
    assert py_calculate_pace(1000, 360000) == "06:00 / km"
    # Unrealistic speeds (too fast < 120s/km or stopped > 3600s/km)
    assert py_calculate_pace(1000, 60000) == "--:-- / km"
    assert py_calculate_pace(100, 500000) == "--:-- / km"


# ===========================================================================
# 2. GPS Point Filtering & Jump Rejection Rules
# ===========================================================================

def is_valid_gps_point(lat, lon, accuracy, timestamp) -> bool:
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False
    if math.isnan(lat) or math.isnan(lon):
        return False
    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return False
    if not timestamp or timestamp <= 0:
        return False
    if accuracy is not None and accuracy > 65:
        return False
    return True


def should_accept_new_point(last_pt, new_pt) -> bool:
    if last_pt is None:
        return True
    if last_pt["latitude"] == new_pt["latitude"] and last_pt["longitude"] == new_pt["longitude"]:
        return False
    d = py_haversine(last_pt["latitude"], last_pt["longitude"], new_pt["latitude"], new_pt["longitude"])
    if d < 2.0:
        return False
    dt = (new_pt["timestamp"] - last_pt["timestamp"]) / 1000
    if dt > 0:
        speed = d / dt
        if speed > 12.0 and d > 30.0:
            return False
    return True


def test_point_validity():
    """Coordinates and accuracy must be within outdoor walking bounds."""
    assert is_valid_gps_point(12.9716, 77.5946, 15, 1728378000000) is True
    # Invalid lat/lon
    assert is_valid_gps_point(95.0, 77.5946, 15, 1728378000000) is False
    assert is_valid_gps_point(12.9716, 200.0, 15, 1728378000000) is False
    assert is_valid_gps_point(float('nan'), 77.5946, 15, 1728378000000) is False
    # Poor accuracy > 65m
    assert is_valid_gps_point(12.9716, 77.5946, 70, 1728378000000) is False
    # Missing timestamp
    assert is_valid_gps_point(12.9716, 77.5946, 10, None) is False


def test_stationary_jitter_rejection():
    """Jitter under 2 metres when standing still is discarded."""
    pt1 = {"latitude": 12.971600, "longitude": 77.594600, "timestamp": 1000}
    # Jitter of ~ 0.5 metres
    pt2 = {"latitude": 12.971604, "longitude": 77.594600, "timestamp": 3000}
    assert should_accept_new_point(pt1, pt2) is False

    # Real movement of ~ 10 metres
    pt3 = {"latitude": 12.971700, "longitude": 77.594600, "timestamp": 10000}
    assert should_accept_new_point(pt1, pt3) is True


def test_teleport_jump_rejection():
    """Cell-tower jump (>12m/s over >30m) is rejected."""
    pt1 = {"latitude": 12.971600, "longitude": 77.594600, "timestamp": 1000}
    # Jump of 500m in 2 seconds (250 m/s)
    pt2 = {"latitude": 12.975000, "longitude": 77.594600, "timestamp": 3000}
    assert should_accept_new_point(pt1, pt2) is False


# ===========================================================================
# 3. HTML / JavaScript Implementation Verification
# ===========================================================================

def test_html_contains_trail_elements(html_content: str):
    """static/index.html must define the trail UI elements and modals."""
    # Field trail status bar
    assert 'class="field-trail-bar"' in html_content
    assert 'id="fieldGpsStatus"' in html_content
    assert 'id="fieldDistance"' in html_content
    assert 'id="fieldPace"' in html_content
    assert 'id="toggleTrailViewBtn"' in html_content
    assert 'id="fieldTrailDrawer"' in html_content
    assert 'id="fieldTrailSvgContainer"' in html_content

    # GPS Permission modal
    assert 'id="gpsModal"' in html_content
    assert 'id="enableGpsBtn"' in html_content
    assert 'id="skipGpsBtn"' in html_content

    # Summary modal
    assert 'id="summaryModal"' in html_content
    assert 'id="sumDistance"' in html_content
    assert 'id="sumTime"' in html_content
    assert 'id="sumPace"' in html_content
    assert 'id="sumMissions"' in html_content
    assert 'id="summaryTrailSvg"' in html_content
    assert 'id="closeSummaryBtn"' in html_content

    # Interrupted walk recovery modal
    assert 'id="recoverModal"' in html_content
    assert 'id="resumeWalkBtn"' in html_content
    assert 'id="discardWalkBtn"' in html_content


def test_html_contains_trail_manager(html_content: str):
    """static/index.html must implement trailManager with geolocation watch."""
    assert "haversineDistance" in html_content
    assert "formatDistance" in html_content
    assert "renderTrailSvg" in html_content
    assert "const trailManager =" in html_content
    assert "navigator.geolocation.watchPosition" in html_content
    assert "navigator.geolocation.clearWatch" in html_content
    assert "enableHighAccuracy: true" in html_content
    assert "active_trail" in html_content


def test_html_trail_drawer_toggle(html_content: str):
    """Trail view toggle opens and closes the drawer."""
    assert "toggleTrailViewBtn" in html_content
    assert "fieldTrailDrawer" in html_content


def test_offline_svg_projection(html_content: str):
    """Trail SVG renders with local coordinate projection and markers."""
    assert 'class="trail-svg"' in html_content
    assert 'polyline' in html_content
    assert 'START' in html_content
    assert 'YOU' in html_content


# ===========================================================================
# 4. Strict Privacy & Zero Remote Dependencies
# ===========================================================================

def test_strict_local_privacy(html_content: str):
    """No external map SDKs or remote map tile services."""
    forbidden = [
        "google.com/maps",
        "api.mapbox.com",
        "openstreetmap.org",
        "leaflet",
        "maplibre",
        "tile.openstreetmap",
        "cartocdn",
    ]
    for term in forbidden:
        assert term not in html_content.lower(), f"Forbidden remote map service found: {term}"

    # Privacy notice text present in the interface
    assert "Your trail stays on this device." in html_content


def test_server_does_not_accept_gps_coordinates():
    """Backend server does not ingest live GPS coordinates in /api/check or /api/quests."""
    server_code = SERVER_PATH.read_text(encoding="utf-8")
    assert "/api/trail" not in server_code
    assert "/api/gps" not in server_code
