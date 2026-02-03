## Purpose

This file gives concise, actionable guidance for AI coding agents working on this repo (Auto Khu Vườn Trên Mây).

## Big picture

- Single-process Python tool that automates an Android game via ADB (primarily LDPlayer). The main entrypoints are `main.py` (GUI default) and the GUI modules under the repo root (`gui_main.py`, `gui_auto_farm.py`, `gui_select_device.py`).
- Core automation logic lives under `core/` and separates device control (`core/adb.py`, `core/adb_helper.py`), image/template detection (`core/image_detection.py`, `core/image.py`), and domain logic (`core/auto_farm.py`, `core/thu_hoach.py`, `core/trong_cay.py`).
- Templates and visual assets are under `assets/items/` and `assets/icon/` and are used by `ImageDetector.find_template()` for decisions.

## Run / developer workflows

- GUI mode (default): run `run_gui.bat` or `python main.py` (no args) — GUI located in `gui_main.py`.
- Console mode: `python main.py --console` or `run_console.bat`.
- Quick scripts: `run_auto_farm.bat`, `run_screenshot_tool.bat`, `test_screenshot.bat` exist for common tasks.
- Device selection is persisted in `selected_device.json`; the GUI chooser is `gui_select_device.py` and helper logic `core/adb_helper.py` tries to discover LDPlayer adb installations.

## Key patterns & conventions

- Lazy imports: GUI/console entrypoints import heavy core modules only when needed (see `main.py`), so long-running processes don't eagerly import OpenCV/ppadb.
- ADB abstraction: Use `core.adb.ADBController` for device actions (`screenshot_full()`, `tap()`, `swipe()`, `input_text()`, `send_touch_sendevent()`). Instantiate with `ADBController(serial=...)`.
- Image detection: Use `core.image_detection.ImageDetector.find_template()` which returns center coordinates of matched templates (BGR numpy arrays expected). Templates live in `assets/items/`.
- Coordinate conventions: UI code uses absolute pixel coordinates for taps/swipes. `core/adb.py` includes coordinate helpers (`px_to_system`, `interpolate_points`) and global `SIZE` from `config.py` can affect transforms.
- Logging: Modules use Python `logging` (module-level `logger = logging.getLogger(__name__)`). Keep logs consistent and avoid print-only changes.

## Integration points / external deps

- ADB (Android Debug Bridge): repo expects `adb` or LDPlayer-provided adb; `core/adb_helper.py` attempts common LDPlayer paths. Tests/dev machines must have ADB accessible.
- ppadb (python-adb wrapper) and OpenCV (`cv2`) are used; check `config.py` for image sizes and constants.
- scrcpy is present under `scrcpy/` for manual interaction and screenshots; some helpers use scrcpy+adb to capture clean screenshots.

## Useful examples

- Capture a screen (returns OpenCV image):
```
adb = ADBController(serial="emulator-5566")
img = adb.screenshot_full()
```
- Find harvest basket template:
```
det = ImageDetector()
pos = det.find_template(img, "assets/items/thu_hoach.png")
if pos: x,y = pos
```
- Use automation flows: create bot with `create_farm_bot(adb, smart=True)` from `core/auto_farm.py` and call `harvest_all()` / `plant_all()`.

## Files to inspect first when changing behavior

- `core/adb.py` — device control and coordinate transforms
- `core/auto_farm.py` and `core/thu_hoach.py` — high-level farm logic
- `core/image_detection.py` and `core/image.py` — template matching and image helpers
- `gui_main.py`, `gui_select_device.py` — how GUI selects devices and starts tasks
- `config.py` — global constants (SIZE, coordinates, template mappings)

## What NOT to assume

- Do NOT assume a fixed emulator name or path; use `core/adb_helper.py` or `selected_device.json` to determine the active device.
- Do NOT change template assets without validating `ImageDetector` thresholds — matching is sensitive to image scale.

## When in doubt

- Run the GUI and use the device selector to reproduce the flow interactively; use `cache/` and `assets/screenshots/` for sample images.

---
If any section is unclear or you want more detail (e.g., a quick start snippet for running a full farm cycle in headless mode), tell me which area to expand. 
