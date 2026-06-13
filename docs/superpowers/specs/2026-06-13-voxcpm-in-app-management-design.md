# VoxCPM In-App Management Design

## Goal

Make VoxCPM usable by ordinary installers without manual PowerShell scripting. The application settings window will manage installation, model storage, service start/stop, health checks, and opt-in auto-start when VoxCPM is selected for pronunciation.

## Approved Product Behavior

- The main application installer does not bundle the multi-GB model or Python virtual environment.
- The installed app includes the VoxCPM setup/service scripts needed to install the optional local service.
- Users can choose both the VoxCPM install root and model cache root in the settings UI.
- Users can start a background install/update from the settings UI and open the install log.
- Users can start or stop the local service from the settings UI.
- The app does not start VoxCPM on application launch by default.
- If the pronunciation engine is `VoxCPM 本地服务` and the user enables `使用时自动启动服务`, the first pronunciation attempt starts the local service if it is already installed.
- If VoxCPM is not installed, pronunciation does not silently download a large model. The app shows a settings/status prompt and lets the user start background installation explicitly.

## Settings Layout

Replace the long single form with a categorized settings dialog:

- `学习`: enable/disable, review interval, activity slowdown, snooze duration.
- `显示`: display mode, card/barrage position, popup duration.
- `发音`: accent, mute, TTS provider, VoxCPM endpoint/timeout, install root, model root, mirror setting, auto-start setting, status and action buttons.
- `快捷键`: all existing hotkey controls.
- `词库`: import and recommended wordbook download actions.

The VoxCPM block exposes three status values: installation, service state, and endpoint. Actions are background install/update, start service, stop service, health check, and open log.

## Architecture

Create a focused `app/voxcpm_service.py` module for local VoxCPM service lifecycle behavior. The controller owns one manager instance, connects it to settings-window signals, and updates the settings window with status changes. The TTS provider remains an HTTP client and does not learn how to install or launch services.

`AppSettings` gains persisted VoxCPM management fields:

- `voxcpm_install_root`
- `voxcpm_model_cache_root`
- `voxcpm_use_model_mirror`
- `voxcpm_auto_start`

## Error Handling

- Invalid install/model paths normalize back to safe local defaults under `%LOCALAPPDATA%\OhMyWord\voxcpm`.
- Endpoint remains restricted to local HTTP hosts.
- Install and service commands stream diagnostics to `install.log` or the existing app logger.
- Background installation failures do not crash the app; they update UI status and show a tray notice.
- Stop only terminates the process tracked by the manager. It does not kill arbitrary processes on port 8808.

## Verification

- Unit tests cover settings normalization/persistence.
- Unit tests cover service manager command construction and status checks with fake processes.
- Unit tests cover controller auto-start behavior with a mocked manager.
- UI tests cover settings dialog round-trip and presence of categorized tabs/action signals.
- Full test suite must pass.
- Because this changes PySide UI and packaging-adjacent behavior, runtime verification must include starting the app or built artifact on Windows and checking the settings UI.
