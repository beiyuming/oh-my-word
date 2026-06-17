# Qt Async VoxCPM Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blocking VoxCPM pronunciation path with a Qt-native asynchronous network and audio pipeline so clicking朗读 no longer stalls the GUI thread.

**Architecture:** Keep `PronunciationService` as the controller-facing facade, preserve `system_qt` behavior, and rebuild only `voxcpm_local` around Qt event-driven I/O. The hot path uses `QNetworkAccessManager`/`QNetworkReply` for async HTTP, `QIODevice` buffering for PCM, and `QAudioSink` or `QMediaPlayer` for playback notifications instead of synchronous `urlopen()`/manual `sleep()` loops.

**Tech Stack:** Python 3.11, PySide6 6.7+, QtCore, QtNetwork, QtMultimedia, unittest/pytest.

---

### Task 1: Lock The Target Behavior In Tests

**Files:**
- Modify: `tests/test_tts.py`
- Modify: `tests/test_controller.py`

- [ ] Add tests proving the old blocking helpers are no longer the runtime path for `voxcpm_local`.
- [ ] Add tests for a Qt-style PCM buffer device: append bytes, emit readable data, drain in pull mode, and support stop/reset.
- [ ] Add tests for `PronunciationService`/`VoxCpmHttpProvider` request acceptance, previous-session cancellation, and playback callback propagation.
- [ ] Add controller tests proving VoxCPM requests do not record `last_pronounced_at` immediately, but do record when playback-started is reported later.
- [ ] Add controller tests for async failure notices and for auto-start no longer doing synchronous health probes in the click path.

### Task 2: Rebuild VoxCPM Playback Around Qt Async I/O

**Files:**
- Modify: `app/tts.py`
- Test: `tests/test_tts.py`

- [ ] Add a `QIODevice`-backed PCM buffer for `QAudioSink.start(device)` pull playback.
- [ ] Add a per-request session object that owns one `QNetworkReply`, optional WAV fallback reply, playback objects, and completion signals.
- [ ] Replace `urllib.request`, manual chunk iteration, `sleep()`, and `processEvents()` with `QNetworkAccessManager`, `QNetworkReply.readyRead`, and signal-driven playback start/failure handling.
- [ ] Keep `/synthesize_stream` as the preferred path and preserve async `/synthesize` fallback for 404/405.
- [ ] Stop the previous active session before starting a new one.

### Task 3: Adapt PronunciationService And Controller To Async Playback Events

**Files:**
- Modify: `app/tts.py`
- Modify: `app/controller.py`
- Test: `tests/test_controller.py`

- [ ] Extend `PronunciationService` with playback lifecycle signals that carry a request tag.
- [ ] Keep `system_qt` synchronous behavior intact, but let `voxcpm_local` report real playback start/failure through signals.
- [ ] Make controller pronunciation requests attach a request tag containing the requested word identity.
- [ ] Record `last_pronounced_at` only when VoxCPM playback actually starts, not when the request is merely accepted.
- [ ] Surface async playback failures through the existing tray notice path without blocking the UI thread.

### Task 4: Remove Synchronous Service Probe From The Click Hot Path

**Files:**
- Modify: `app/controller.py`
- Modify: `app/voxcpm_service.py`
- Test: `tests/test_controller.py`
- Test: `tests/test_voxcpm_service_manager.py`

- [ ] Remove the synchronous `health_check()` call from `_maybe_start_voxcpm_for_pronunciation()`.
- [ ] Ensure `start_service()` no longer performs a blocking `/health` probe before spawning the service process.
- [ ] Preserve existing “not installed” and “starting, please retry” UX.
- [ ] Keep settings-page manual health checks working as an explicit user action.

### Task 5: Verification And Contract Updates

**Files:**
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `docs/specs/app-controller.md`
- Modify: `memory/00-current-status.md`

- [ ] Update the stable docs to reflect the Qt async VoxCPM path and the new “record pronunciation on playback-start” rule.
- [ ] Run targeted tests for TTS/controller/service-manager slices.
- [ ] Run `py -3.11 -m pytest tests -q`.
- [ ] If code changes affect visible pronunciation behavior, note that Windows runtime click-and-audio verification is still required before claiming desktop-level completion.
