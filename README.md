# oh my word (Python)

A portable Windows-first rewrite of `oh my word` built with `Python + PySide6`.

## Scope

- System tray first
- Two display modes: `card` and `barrage`
- Offline pronunciation first
- Local JSON settings and learning state
- Directory-based wordbooks with a bundled Kaoyan wordbook
- User-imported JSON/CSV wordbooks and an optional recommended NETEM wordbook download
- Recognition review state with FSRS-style stability/difficulty fields

## Layout

```text
main.py
app/
data/wordbooks/
storage/
build/build_exe.ps1
tests/
requirements.txt
```

## Run From Source

1. Create a virtual environment if you want one.
2. Install dependencies:

```powershell
py -3.11 -m pip install -r requirements.txt
```

3. Start the app:

```powershell
py -3.11 main.py
```

The app starts in the tray. On first launch it creates missing runtime files and opens the settings window.

## Default Hotkeys

- `Ctrl+Alt+1`: pronounce current word
- `Ctrl+Alt+2`: toggle popup details
- `Ctrl+Alt+3`: trigger next word now
- `Ctrl+Alt+4`: mark current word as mastered

Hotkeys can be changed in settings by clicking a shortcut field and pressing the desired key combination.

## Runtime Files

- `storage/settings.json`
- `storage/learning_state.json`
- `storage/app.log`

`settings.json` stores user configuration only. `learning_state.json` stores recent words plus per-word progress fields such as `show_count`, timestamps, review counts, `due_at`, `stability`, `difficulty`, and `mastered`.

## Wordbooks

The app loads every JSON file under `data/wordbooks/` in filename order.

- Later files override earlier duplicate words.
- Broken JSON files are skipped and logged.
- If no usable wordbook exists, the app recreates the default `kaoyan_core.json`.
- Settings can import local JSON or CSV wordbooks and convert them to the app's local JSON format.
- Settings can download a recommended NETEM wordbook after a confirmation dialog that shows source, license, and target path.

Each entry uses this shape:

```json
{
  "word": "abandon",
  "ipa": "/əˈbændən/",
  "part_of_speech": "verb",
  "definitions": ["放弃", "抛弃"],
  "example_sentence": "Many exam takers refuse to abandon their daily review plan.",
  "example_translation": "很多考研学生不会放弃每天的复习计划。"
}
```

Imported JSON can either use this exact shape or common alternatives such as `word`, `term`, `wordHead`, `translation`, `definitions`, `tranCn`, and nested `content` objects. Imported CSV files should contain at least a word column (`word`, `term`, or similar) and a definition/translation column.

The recommended download source is:

- Source: `https://github.com/exam-data/NETEMVocabulary`
- Raw data: `https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json`
- Wordbook license: `CC BY-NC-SA 4.0`
- Local target: `data/wordbooks/kaoyan_full.json`

## Tests

Run logic tests with:

```powershell
py -3.11 -m pytest tests -q
```

The current test suite focuses on:

- settings normalization and persistence
- learning state round-trip
- wordbook loading and selection rules
- scheduler pure logic

## Build EXE

```powershell
.\build\build_exe.ps1
```

The script uses `PyInstaller` and places the bundled output under `dist/`.

## Notes

- This first version targets Windows only.
- Global hotkeys use the native Windows `RegisterHotKey` API.
- Offline pronunciation prefers `QtTextToSpeech` and falls back to any available English voice.
