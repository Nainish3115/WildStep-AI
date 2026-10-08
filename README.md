# WildStep AI

**Local AI. Real-world missions. Zero scrolling.**

Developer & Maintainer: **Nainish Jaiswal**

> WildStep AI is an offline-first outdoor companion powered by local open-weight AI. It prepares personalized real-world missions, helps verify discoveries, and creates a local adventure journal — while deliberately minimizing the time the user spends looking at a screen.

---

## What is WildStep AI?

WildStep AI turns outdoor walks into focused real-world discovery sessions without screen addiction. The verified application workflow operates as follows:

1. **User enters an outdoor location and context:** Provide where you plan to walk (e.g., local park, lake trail, neighbourhood) and who is joining (e.g., solo, with children).
2. **Local Gemma generates an outdoor scavenger mission:** A local open-weight model writes a 6-item mission card adapted to the actual geographical context, current month, and seasonal climate.
3. **User receives the mission:** The card presents concrete, visible outdoor objectives with assigned point values and emojis. Users can inspect the card or use browser print to take a physical paper copy.
4. **User enters Phone Away mode:** Triggering the departure timer opens a dedicated full-screen lockout view designed to keep the phone in your pocket during the walk.
5. **User goes outside:** The user walks outdoors with their phone put away, only retrieving the device to take photos of discoveries.
6. **User photographs discoveries:** Native camera photos capture nature elements without any immediate in-field appraisal or scrolling.
7. **Local vision inference evaluates evidence:** Back home, the user drops photos into the application. A local multimodal vision model evaluates each photograph against active mission objectives.
8. **EXIF/GPS information is processed locally:** Camera capture timestamps and geographic coordinates embedded in the photo headers are extracted and validated entirely on the local machine.
9. **The application produces a local walk journal and route visualization:** A chronological field journal is generated alongside an offline SVG route map linking the photo locations.

---

## Why WildStep AI?

Modern mobile outdoor applications frequently produce the opposite of their intended effect: users spend their time outdoors staring at screens, checking feeds, consulting social leaderboards, or arguing with inaccurate classifiers.

WildStep AI is built on a distinct design principle:

> **The application is designed to use AI briefly so that the user can spend more time away from the screen.**

You spend two minutes with AI before leaving, keep the device in your pocket for an hour while exploring the physical world, and spend two minutes reviewing your verified discoveries upon returning.

---

## Local AI

WildStep AI relies entirely on local open-weight models executed on your hardware:

* **Inference Engine:** Powered by [Ollama](https://ollama.com), running locally over `http://127.0.0.1:11434`.
* **Model:** Default configured to Google's open-weight `gemma4:e2b` (quantized local vision and instruction model), configurable via `QUEST_MODEL`.
* **Structured Generation:** Mission generation enforces strict JSON Schemas (`QUEST_SCHEMA`) through Ollama's constrained grammar generation, preventing broken output formats.
* **Local Vision Evidence Verification:** Rather than performing brittle fine-grained species identification that frequently misleads users, the model is prompted as an impartial scavenger hunt judge. It answers coarse observational questions: *Is the requested subject clearly present? Is it the main subject of the frame? What is the specific visible evidence?* Points are awarded only when both the completion flag and main-subject flag are validated with concrete evidence descriptions.

---

## Privacy

* **Zero Cloud APIs:** No OpenAI, Google Cloud, Anthropic, or remote telemetry endpoints.
* **Photos Never Leave Your Machine:** All image files are read, downsampled, and evaluated directly in host memory or local storage.
* **Location Data Remains Private:** GPS coordinates extracted from photo EXIF tags are processed locally and rendered into self-contained vector paths. No mapping provider ever receives your location traces.

---

## Offline Operation

WildStep AI is architected from the ground up to operate without an active internet connection once initial dependencies and models are downloaded:

* **Zero Remote Assets:** No external CDNs, remote web fonts, analytics beacons, or remote style libraries. All assets are served from the local HTTP server.
* **Tile-Free Route Rendering:** Route maps are generated using an internal mathematical projection into pure SVG polylines directly from photo GPS coordinates. No map tile downloads (OpenStreetMap, Mapbox, Google Maps) are needed.
* **Runtime Locality:** All LLM inference, EXIF extraction, and journal construction run on the local machine.

*(Note: While the server and web application run completely offline, installable PWA caching and service workers are not yet implemented in this foundation phase; initial page loading requires connecting to the running local server).*

---

## Current Features

* **Contextual Mission Synthesis:** Synthesizes balanced 6-objective outdoor scavenger missions tailored to season, biome, and walking companions.
* **Instant Fallback Missions:** Instant non-LLM mission generation sourced from a curated internal safe pool.
* **Phone Away Mode:** Dedicated full-screen focus overlay recording start time and discouraging in-walk screen usage.
* **Dual-Condition Vision Verification:** Checks whether an item is present, whether it represents the main subject, and whether verifiable evidence exists.
* **EXIF Date & GPS Extraction:** Automatically reads photo capture timestamps (`DateTimeOriginal`) and geolocation coordinates (`GPSInfo`).
* **Offline Vector Route Map:** Plots walk path geometry and calculates total distance between photographic waypoints using pure mathematical SVG.
* **Chronological Walk Journal:** Visual timeline organizing photographs, capture times, verified mission badges, and missing metadata warnings.
* **Optional Durable Execution (Temporal):** Optional fault-tolerant batch photo processing backed by an embedded local Temporal dev server, allowing browser tabs to close during long verification batches.

---

## Architecture

```mermaid
flowchart TD
    U[User] --> W[WildStep AI Web Client]

    W --> Q[Mission API (/api/quests)]
    Q --> O[Local Ollama Daemon]
    O --> G[Local Open-Weight Model (Gemma)]

    W --> P[Photo Processing (/api/check)]
    P --> X[Pillow EXIF / GPS Parser]
    P --> V[Vision Evidence Judge]
    V --> O

    X --> R[Offline SVG Route Renderer]
    V --> J[Local Walk Journal]
    R --> J

    J --> U
```

---

## Installation

### Prerequisites
1. Python 3.10+ installed.
2. [Ollama](https://ollama.com) installed and running locally.

### Steps

```bash
# 1. Pull the local open-weight vision model
ollama pull gemma4:e2b

# 2. Install required Python packages (Pillow)
pip install -r requirements.txt

# 3. Start the WildStep AI server
python server.py
```

Open `http://127.0.0.1:8777` in your browser.

---

## Configuration

The application is configured using environment variables (`WILDSTEP_*` variables take primary precedence, with `QUEST_*` supported for backward compatibility):

| Preferred Variable | Compatibility Fallback | Default | Description |
|---|---|---|---|
| `WILDSTEP_OLLAMA_URL` | `QUEST_OLLAMA_URL` | `http://127.0.0.1:11434` | URL of the local Ollama HTTP API |
| `WILDSTEP_MODEL` | `QUEST_MODEL` | `gemma4:e2b` | Open-weight model tag pulled in Ollama |
| `WILDSTEP_HOST` | `QUEST_HOST` | `127.0.0.1` | Host address to bind the HTTP server |
| `WILDSTEP_PORT` | `QUEST_PORT` | `8777` | Port number for the HTTP server |
| `WILDSTEP_TEMPORAL` | `QUEST_TEMPORAL` | `127.0.0.1:7233` | Host and port for optional local Temporal server |
| `WILDSTEP_DATA` | `QUEST_DATA` | `~/.wildstep-ai` | Storage directory for durable walk caches (falls back to `~/.outside-quest` if present) |

---

## Testing

*Automated test suites are not yet implemented in this repository.*

The current codebase includes manual test photographs in `samples/` and synthetic EXIF walk data in `samples/demo-walk/`. An automated test suite covering safety filters, EXIF parsing, and Ollama integration will be implemented in subsequent phases.

---

## Safety

WildStep AI enforces physical and observational safety using deterministic code rather than trusting raw model outputs:

* **Deterministic Blacklist (`UNSAFE` regex):** Discards any mission objectives suggesting climbing, swimming, wading, entering water, touching wildlife, picking, eating, tasting, feeding, pursuing animals, trespassing, private property, night walks, or busy roads and railway tracks.
* **Mandatory Caution Flags (`PHOTO_ONLY` regex):** Automatically appends `(photo only, don't touch)` to any mention of mushrooms, fungi, berries, nests, or eggs.
* **Safe Fallback Pool (`SAFE_POOL`):** Any objective flagged by safety filtering or failed LLM responses is automatically replaced with proven, low-risk observation goals from a built-in safe catalog.

---

## License & Attribution

WildStep AI is open-source software released under the **MIT License**.

* **WildStep AI Code & Modifications:** Copyright (c) 2026 **Nainish Jaiswal**.
* **Third-Party Media:** Nature sample photographs from Wikimedia Commons under Creative Commons licenses.

For complete license text, see [`LICENSE`](LICENSE).  
For detailed component provenance, see [`ATTRIBUTIONS.md`](ATTRIBUTIONS.md).  
For third-party photo credits, see [`samples/CREDITS.md`](samples/CREDITS.md).
