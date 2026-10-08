"""Tests for Outdoor Field Mode in WildStep AI.

Verifies the DOM structure, accessibility attributes, mobile camera capture configuration,
high-contrast outdoor CSS styling, and client-side logic contracts for the zero-scrolling
Outdoor Field Mode.
"""

from pathlib import Path
import re
import pytest

INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"


@pytest.fixture(scope="module")
def html_content() -> str:
    """Loads static/index.html content."""
    assert INDEX_HTML.exists(), "static/index.html must exist"
    return INDEX_HTML.read_text(encoding="utf-8")


def test_field_mode_container_exists(html_content: str):
    """The Field Mode container must exist with accessible role and label."""
    assert 'id="fieldMode"' in html_content
    assert 'role="region"' in html_content
    assert 'aria-label="Outdoor Field Mode"' in html_content


def test_field_mode_entry_points(html_content: str):
    """Both the mission card and the phone-away modal must have triggers to enter Field Mode."""
    assert 'id="openField"' in html_content
    assert 'id="awayField"' in html_content


def test_field_mode_camera_input(html_content: str):
    """Direct camera capture must use environment capture and accept image/*."""
    pattern = r'<input\s+type="file"\s+id="fieldCamera"[^>]*>'
    match = re.search(pattern, html_content)
    assert match is not None, "Field camera input element not found"
    tag = match.group(0)
    assert 'accept="image/*"' in tag, "Camera input must accept image/*"
    assert 'capture="environment"' in tag, "Camera input must specify capture=environment for mobile"


def test_field_mode_mission_elements(html_content: str):
    """Field Mode must include elements for title, emoji, objective text, and status badge."""
    assert 'id="fieldProgressText"' in html_content
    assert 'id="fieldEmoji"' in html_content
    assert 'id="fieldText"' in html_content
    assert 'id="fieldStatus"' in html_content


def test_field_mode_live_feedback(html_content: str):
    """Feedback container must have aria-live='polite' and role='status' for accessibility."""
    assert 'id="fieldFeedback"' in html_content
    pattern = r'<div\s+id="fieldFeedback"[^>]*>'
    match = re.search(pattern, html_content)
    assert match is not None
    tag = match.group(0)
    assert 'role="status"' in tag
    assert 'aria-live="polite"' in tag


def test_field_mode_navigation_controls(html_content: str):
    """Field Mode must include Previous and Next controls with aria labels."""
    assert 'id="fieldPrev"' in html_content
    assert 'id="fieldNext"' in html_content
    assert 'aria-label="Previous mission"' in html_content
    assert 'aria-label="Next mission"' in html_content


def test_field_mode_walk_timer_and_pocket_mode(html_content: str):
    """Walk timer and pocket mode screen lock container must exist."""
    assert 'id="fieldTimer"' in html_content
    assert 'id="fieldPocketBtn"' in html_content
    assert 'id="pocketOverlay"' in html_content
    assert 'id="pocketClock"' in html_content


def test_outdoor_css_contrast_and_safe_areas(html_content: str):
    """CSS must define outdoor sunlight-readable palette and safe-area insets."""
    assert "#fieldMode" in html_content
    assert "safe-area-inset-top" in html_content
    assert "touch-action: manipulation" in html_content
    # Glare-resistant dark background
    assert "#081107" in html_content
    # High-visibility neon green accent
    assert "#4ade80" in html_content


def test_pocket_mode_oled_black_and_z_index(html_content: str):
    """Pocket mode overlay must use pure black (#000) for OLED power saving and high z-index."""
    assert "#pocketOverlay" in html_content
    assert "background: #000" in html_content or "background:#000" in html_content


def test_safe_haptic_fallback_implementation(html_content: str):
    """Haptic feedback function must check navigator.vibrate existence defensively."""
    assert "function triggerHaptic(pattern)" in html_content
    assert "'vibrate' in navigator" in html_content


def test_field_mode_auto_advance_logic(html_content: str):
    """Script must contain function to auto-advance to next unfinished mission."""
    assert "advanceToNextUnfinished" in html_content
    assert "openFieldMode" in html_content
    assert "closeFieldMode" in html_content
    assert "startWalkTimer" in html_content


def test_print_stylesheet_hides_field_mode(html_content: str):
    """Print media styles must hide field mode and pocket overlay."""
    assert "@media print" in html_content
    pattern = r'@media print\s*\{[\s\S]*?#fieldMode[\s\S]*?\}'
    assert re.search(pattern, html_content) is not None, "Print stylesheet must exclude #fieldMode"
    assert re.search(r'@media print\s*\{[\s\S]*?#pocketOverlay[\s\S]*?\}', html_content) is not None

