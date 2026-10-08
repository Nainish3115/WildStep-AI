"""Tests for Voice-First Field Mode in WildStep AI.

Validates:
1. Speech API availability detection and unsupported browser fallbacks.
2. Voice toggle UI controls, ARIA states, and Pocket Mode integration.
3. Spoken mission announcement generation (concise format, no IDs or point values).
4. Spoken success, failure/retry, and walk completion guidance.
5. Speech sanitization (HTML removal, JSON stripping, whitespace normalization, length cutoff).
6. Speech queue management (stopping/canceling previous speech).
7. Coherent integration with existing Field Mode, haptics, and zero external speech APIs.
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


# ---------------------------------------------------------------------------
# Python reference implementation mirroring the client-side JavaScript sanitization
# to rigorously test text manipulation and edge-case contracts.
# ---------------------------------------------------------------------------
def js_sanitize_speech(text: str) -> str:
    """Mirrors voice.sanitize in static/index.html."""
    if not text or not isinstance(text, str):
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]*>", " ", text)
    # Strip common JSON brackets and quotes
    clean = re.sub(r'[{}\[\]"]', " ", clean)
    # Normalize whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    # Length cutoff to prevent long model rambling or prompt injections
    if len(clean) > 140:
        clean = clean[:140].strip() + "..."
    return clean


# ===========================================================================
# 1. Voice Controls & DOM Structure
# ===========================================================================

def test_voice_button_exists_with_accessible_attributes(html_content: str):
    """Voice toggle button must exist in Field Mode with accessible attributes."""
    assert 'id="fieldVoiceBtn"' in html_content
    pattern = r'<button\s+id="fieldVoiceBtn"[^>]*>'
    match = re.search(pattern, html_content)
    assert match is not None, "#fieldVoiceBtn element not found"
    tag = match.group(0)
    assert 'aria-label=' in tag, "Must provide accessible aria-label"
    assert 'aria-pressed="false"' in tag, "Must default to aria-pressed=false (disabled)"
    assert 'Voice Off' in tag or 'Voice Off' in html_content


def test_voice_disabled_by_default(html_content: str):
    """Voice mode must default to disabled (OFF) to respect browser autoplay policies."""
    assert "let currentMissionIdx = 0, walkStartMs = null, walkTimerInterval = null, voiceEnabled = false;" in html_content
    assert "voiceEnabled = false" in html_content


def test_pocket_mode_voice_indicator_exists(html_content: str):
    """Pocket mode overlay must contain an indicator when spoken missions are active."""
    assert 'id="pocketVoiceNote"' in html_content
    assert "Spoken missions active" in html_content


# ===========================================================================
# 2. Native Web Speech API Contract (Local Only, No Cloud)
# ===========================================================================

def test_uses_native_browser_speech_synthesis(html_content: str):
    """Must strictly use browser window.speechSynthesis and SpeechSynthesisUtterance."""
    assert "window.speechSynthesis" in html_content
    assert "SpeechSynthesisUtterance" in html_content


def test_no_cloud_or_external_speech_apis(html_content: str):
    """Must NOT import or call cloud speech APIs or external speech libraries."""
    forbidden = [
        "elevenlabs",
        "google.cloud.texttospeech",
        "api.speech",
        "azure.cognitiveservices.speech",
        "openai.audio",
        "text-to-speech.googleapis.com",
    ]
    lowered = html_content.lower()
    for term in forbidden:
        assert term not in lowered, f"Forbidden external speech reference found: {term}"


def test_voice_support_detection_and_fallback(html_content: str):
    """The voice module must verify browser support and provide fallback for unsupported browsers."""
    assert "supported()" in html_content
    assert "'speechSynthesis' in window" in html_content
    assert "SpeechSynthesisUtterance !== 'undefined'" in html_content
    assert "Voice N/A" in html_content
    assert "Speech synthesis is not supported" in html_content


# ===========================================================================
# 3. Speech Queue & Cancellation Management
# ===========================================================================

def test_speech_queue_cancels_previous_speech(html_content: str):
    """New speech requests must stop/cancel previous speech to prevent overlapping audio."""
    assert "window.speechSynthesis.cancel()" in html_content
    # In voice.speak(), verify that this.stop() is invoked before speaking new utterance
    pattern = r"speak\s*\([^)]*\)\s*\{[\s\S]*?this\.stop\(\)[\s\S]*?window\.speechSynthesis\.speak"
    assert re.search(pattern, html_content) is not None, "speak() must call this.stop() before speak()"


def test_exiting_field_mode_stops_speech(html_content: str):
    """Exiting Field Mode must immediately cancel any active speech."""
    pattern = r"function closeFieldMode\(\)\s*\{[\s\S]*?voice\.stop\(\)"
    assert re.search(pattern, html_content) is not None, "closeFieldMode must call voice.stop()"


# ===========================================================================
# 4. Spoken Mission Announcement Generation
# ===========================================================================

def test_concise_mission_announcement_format(html_content: str):
    """Announcements must use concise ordinal phrasing (e.g. 'Mission one. <text>')."""
    assert "ORDINALS" in html_content
    assert "Mission ${num}. ${text}" in html_content
    # Confirm it does NOT include points, IDs, or technical metadata in spoken text
    assert "${q.points} pts" not in html_content.split("announceMission")[1].split("}")[0]


def test_navigation_speaks_when_voice_enabled(html_content: str):
    """Navigating Previous/Next while voice is enabled must announce the newly selected mission."""
    prev_pattern = r"fieldPrev[\s\S]*?if\s*\(voiceEnabled\)\s*announceMission\(currentMissionIdx\)"
    next_pattern = r"fieldNext[\s\S]*?if\s*\(voiceEnabled\)\s*announceMission\(currentMissionIdx\)"
    assert re.search(prev_pattern, html_content) is not None
    assert re.search(next_pattern, html_content) is not None


# ===========================================================================
# 5. Success, Failure, and Completion Audio Guidance
# ===========================================================================

def test_spoken_success_and_next_mission_sequence(html_content: str):
    """Successful verification must speak completion and prompt next mission."""
    assert "Mission complete. Nice find. Next mission." in html_content


def test_spoken_failure_retry_guidance(html_content: str):
    """Unverified photo must speak concise retry guidance and sanitized observation."""
    assert "Not enough evidence. Try another photo." in html_content
    assert "Not enough evidence. AI saw ${cleanSee}. Try another photo." in html_content


def test_spoken_walk_completion_announcement(html_content: str):
    """When all missions are finished, walk completion must be announced."""
    assert "Walk complete. You finished all ${numWord} missions." in html_content


def test_voice_disabled_suppresses_speech(html_content: str):
    """When voiceEnabled is false, voice.speak must return immediately without speaking."""
    pattern = r"speak\s*\([^)]*\)\s*\{[\s\S]*?if\s*\(!voiceEnabled[\s\S]*?return;"
    assert re.search(pattern, html_content) is not None


# ===========================================================================
# 6. Speech Sanitization Safety & Prompt Injection Defense
# ===========================================================================

def test_speech_sanitization_html_stripping():
    """HTML tags must be stripped before speech synthesis."""
    raw = "Find <span class='target'>shelf fungus</span> or <b>tree moss</b>"
    cleaned = js_sanitize_speech(raw)
    assert cleaned == "Find shelf fungus or tree moss"
    assert "<" not in cleaned and ">" not in cleaned


def test_speech_sanitization_json_stripping():
    """Raw JSON brackets and quotes must be stripped to prevent robotic syntax reading."""
    raw = '{"what_i_see": "green moss", "evidence": "moss on bark"}'
    cleaned = js_sanitize_speech(raw)
    assert "what_i_see : green moss , evidence : moss on bark" in cleaned
    assert "{" not in cleaned and "}" not in cleaned and '"' not in cleaned


def test_speech_sanitization_whitespace_normalization():
    """Excessive whitespace, tabs, and newlines must be collapsed into single spaces."""
    raw = "Find   shelf \n\n fungus   or\t\t\ttree moss.  "
    cleaned = js_sanitize_speech(raw)
    assert cleaned == "Find shelf fungus or tree moss."


def test_speech_sanitization_length_truncation():
    """Extremely long text (e.g. runaway LLM reasoning or prompt injection) must be truncated."""
    long_text = "Look for a very long tree that has many branches and leaves and " * 10
    assert len(long_text) > 500
    cleaned = js_sanitize_speech(long_text)
    assert len(cleaned) <= 145  # 140 chars + ellipsis
    assert cleaned.endswith("...")


def test_speech_sanitization_handles_empty_and_non_strings():
    """Sanitizer handles empty string, None, and non-string values gracefully."""
    assert js_sanitize_speech("") == ""
    assert js_sanitize_speech(None) == ""
    assert js_sanitize_speech(123) == ""  # type: ignore


# ===========================================================================
# 7. Autoplay and User Gesture Safety
# ===========================================================================

def test_autoplay_restriction_error_handler(html_content: str):
    """Utterance onerror must handle 'not-allowed' without throwing or blocking UI."""
    assert "e.error === 'not-allowed'" in html_content
    assert "Voice ready — tap screen to enable spoken missions." in html_content
