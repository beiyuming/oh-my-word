# Popup Auto Pronounce Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add settings-controlled automatic pronunciation when a word popup appears, with a configurable delay before playback starts.

**Architecture:** Extend `AppSettings` and the pronunciation settings UI with a boolean toggle and delay value, then let `AppController` own a single-shot timer that schedules and cancels automatic pronunciation across both card and barrage popups.

**Tech Stack:** Python 3.11, PySide6 `QTimer`, dataclasses, unittest/pytest

---

## File Map

- Modify: `app/models.py`
- Modify: `app/settings.py`
- Modify: `app/settings_window.py`
- Modify: `app/controller.py`
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `README.md`
- Test: `tests/test_settings.py`
- Test: `tests/test_settings_window.py`
- Test: `tests/test_controller.py`

### Task 1: Add the new settings fields and normalization

**Files:**
- Modify: `app/models.py`
- Modify: `app/settings.py`
- Test: `tests/test_settings.py`

- [ ] Add failing tests for default values, invalid payload normalization, and persisted JSON payload for `auto_pronounce_on_popup` and `auto_pronounce_delay_seconds`.
- [ ] Run the focused settings tests and confirm the new assertions fail for the expected missing-field reason.
- [ ] Add the new defaults to `AppSettings`, normalize them in `normalize_settings()`, and persist them in `settings_to_dict()`.
- [ ] Re-run the focused settings tests and confirm they pass.

### Task 2: Expose the new controls in the settings dialog

**Files:**
- Modify: `app/settings_window.py`
- Test: `tests/test_settings_window.py`

- [ ] Add failing settings dialog tests that round-trip the two new fields and verify the new widgets live in the pronunciation tab.
- [ ] Run the focused settings dialog tests and confirm they fail because the widgets/round-trip do not exist yet.
- [ ] Add the checkbox and delay spin box, wire them into `set_settings()` and `get_settings()`, and keep the controls in the pronunciation group.
- [ ] Re-run the focused settings dialog tests and confirm they pass.

### Task 3: Schedule and cancel automatic pronunciation in the controller

**Files:**
- Modify: `app/controller.py`
- Test: `tests/test_controller.py`

- [ ] Add failing controller tests for: scheduling on popup show, not scheduling when disabled, cancelling on manual pronunciation, and ignoring stale/closed popups when the timer fires.
- [ ] Run the focused controller tests and confirm they fail for the expected missing-timer behavior.
- [ ] Add a single-shot controller timer plus helper methods to schedule, cancel, and fire automatic pronunciation using the existing `pronounce_current_word()` path.
- [ ] Re-run the focused controller tests and confirm they pass.

### Task 4: Update stable docs and verify

**Files:**
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `README.md`

- [ ] Document the two new settings fields, their defaults, and controller-owned trigger semantics in the stable docs.
- [ ] Run `tests/test_settings.py tests/test_settings_window.py tests/test_controller.py`.
- [ ] Run the full suite.
