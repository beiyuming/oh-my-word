# VoxCPM2 Runtime Import Design

## Goal

Keep `VoxCPM 2` as the local pronunciation engine while removing ordinary users' dependence on local Python, `pip install`, runtime probing, and first-run model download. The desktop app will import a prebuilt VoxCPM2 runtime package from GitHub Release assets, validate it against the current Windows + NVIDIA environment, unpack it into the existing local companion-process layout, and then manage it through the current settings/service lifecycle.

## Chosen Product Direction

The approved direction is:

- Keep the current `voxcpm_local` companion-process architecture and local HTTP endpoint.
- Do not switch to `NanoVLLM-VoxCPM`; it is a Linux GPU service path, not the target Windows local deployment path.
- Do not switch to `VoxCPM.cpp`; it improves native deployment shape but does not support `VoxCPM 2`.
- Replace the primary end-user install path for VoxCPM with `导入 VoxCPM 运行时包`.
- Publish multiple prebuilt runtime packages per GitHub Release, each tied to a validated Windows x64 + NVIDIA + CUDA/Torch matrix.
- Treat the current PowerShell script installer as a secondary/legacy path rather than the preferred path for ordinary users.

This trades universal compatibility for a smaller, explicit support matrix that the product can actually validate and explain.

## Supported Environment Matrix

The app should publish and document runtime support as a hard matrix, not a best-effort promise.

Base product constraints:

- `Windows 10/11 x64`
- `NVIDIA GPU`
- `VoxCPM 2`
- local companion process only; no cloud endpoint and no remote provider token flow

Recommended end-user requirements:

- `8 GB+ VRAM`
- `15 GB+` free disk space in the application/runtime target area
- NVIDIA driver version at or above the runtime package's declared minimum

Runtime packages are matrix-specific. A single package does not attempt to support all Windows GPU environments. Example package IDs:

- `voxcpm2-runtime-win-x64-cu124-r1`
- `voxcpm2-runtime-win-x64-cu128-r1`

The application must tell the user which matrix is supported and why a given package is incompatible on the current machine.

## Release Assets

Each app release continues to publish the main desktop installer separately from VoxCPM runtime packages.

Expected asset naming:

- main app installer: `oh-my-word-setup-vX.Y.Z.exe`
- runtime package: `voxcpm2-runtime-win-x64-cu124-r1.zip`
- checksum file: `voxcpm2-runtime-win-x64-cu124-r1.sha256`
- runtime notes: `voxcpm2-runtime-win-x64-cu124-r1.md`

The runtime package revision (`r1`, `r2`, ...) is independent from the app version. A new app release may reuse an existing validated runtime package, and a runtime package may be revised without changing the app's semantic version.

## Runtime Package Layout

The runtime package is a zip with a strict, validated top-level layout:

- `manifest.json`
- `runtime/`

Inside `runtime/`, the package must already match the shape that the app will activate as the live VoxCPM root:

- `runtime/.venv/`
- `runtime/service/`
- `runtime/models/`
- `runtime/start_service.ps1`
- `runtime/healthcheck.ps1`

The package must contain a fully prepared runtime for one supported matrix:

- fixed private Python runtime
- fixed PyTorch/CUDA dependency set
- VoxCPM service files
- bundled VoxCPM2 model files
- startup and health-check scripts

The package is product-specific. The app should not accept arbitrary user-assembled Python/Torch/model directories as a supported import path.

## Manifest Contract

`manifest.json` must be treated as the package contract. Required fields:

- `runtime_id`
- `runtime_version`
- `target_os`
- `target_arch`
- `cuda_tag`
- `min_driver_version`
- `python_version`
- `torch_version`
- `model_id`
- `model_version`
- `expected_layout_version`
- `package_size`
- `file_hashes`
- `built_at`

`file_hashes` must cover the critical runtime files that the application relies on to trust the package. At minimum this includes startup script(s), service code, Python runtime entrypoints inside `runtime/.venv`, and model artifacts needed for a successful health/start check.

## Import Entry and UI

The preferred settings entry changes from "install VoxCPM" to `导入 VoxCPM 运行时包`.

Primary actions in the pronunciation settings section:

- `导入 VoxCPM 运行时包`
- `检查运行时`
- `启动服务`
- `停止服务`
- `打开日志目录`

The existing background script-based install/update entry may remain, but it should become secondary and clearly positioned as a fallback/legacy path.

The status area should display:

- runtime status: `未导入 / 已导入 / 不兼容 / 损坏`
- runtime ID
- CUDA tag
- minimum driver requirement
- model version
- install path
- service status: `未启动 / 启动中 / 运行中 / 异常`

## Import Flow

The import flow must avoid mutating the active runtime until the new package is fully validated.

### Phase 1: User Selection

1. User clicks `导入 VoxCPM 运行时包`.
2. User selects a runtime zip from disk.

### Phase 2: Read-Only Preflight

Before any extraction into the active runtime path, the app checks:

- zip readability
- presence of `manifest.json`
- presence of `runtime/`
- package filename vs manifest identity
- host OS is `Windows x64`
- NVIDIA GPU presence
- current NVIDIA driver version satisfies `min_driver_version`
- free disk space is sufficient
- active VoxCPM service is not running, or the user explicitly stops it first

If preflight fails, import stops with a reason-specific error message and no filesystem mutation.

### Phase 3: User Confirmation

If preflight passes, show a confirmation dialog containing:

- runtime ID
- CUDA tag
- minimum driver requirement
- model version
- target extraction path
- expected disk usage

### Phase 4: Staging Extraction

Extract into a staging directory under the existing VoxCPM root, for example:

`<app-dir>\tts\voxcpm\.import-staging\`

The staging area must be disposable and isolated from the active runtime. The extracted `runtime/` subtree is the candidate active runtime root.

### Phase 5: Staging Validation

After extraction, validate again inside staging:

- expected layout version
- required file set
- manifest/file hash integrity
- `runtime/.venv` presence
- startup script presence
- service script presence
- model artifact presence
- health-check script availability

Run a local staging health/start validation before activation. The staging validation should prove that the imported runtime can launch its local service and pass the health probe on the user's machine.

### Phase 6: Activation

Only after staging validation passes should the app activate the runtime:

- rename existing active runtime to a timestamped backup
- promote the extracted `runtime/` subtree to the active runtime path
- refresh runtime status in the settings UI

## Active Runtime Path and Backward Compatibility

The first implementation should keep the active runtime path compatible with the current product defaults:

`<app-dir>\tts\voxcpm`

This preserves compatibility with:

- current settings defaults
- local logs and start script expectations
- current `voxcpm_local` service management shape
- current local endpoint assumptions

The import feature changes the source of the runtime, not the fundamental runtime location model.

## Rollback and Backup Strategy

The import process must be recoverable.

Required behavior:

- never unpack directly over the active runtime
- keep the active runtime untouched until staging validation succeeds
- before activation, rename the previous runtime to a timestamped backup
- if activation fails, restore the backup automatically
- keep at least the most recent backup for manual recovery

This is required to avoid leaving the app in a half-imported state.

## Error Handling

The UI and logs must classify import failures into concrete categories. At minimum:

- invalid package structure
- unsupported host environment
- insufficient NVIDIA driver version
- insufficient free disk space
- file integrity/hash mismatch
- incomplete model payload
- active service still running
- staging health check failed

Messages must tell the user what to do next. For example, driver mismatch should identify the required minimum driver or tell the user to import a different runtime package.

## Interaction with Existing Service Management

The import feature should reuse the existing `voxcpm_local` service lifecycle shape:

- local service remains behind the same local HTTP endpoint
- start/stop/health-check remain settings-driven actions
- auto-start-on-pronunciation behavior remains unchanged conceptually

However, runtime presence and integrity checks now become richer:

- `installed` no longer means only "venv + start script exist"
- it also means the imported runtime package is structurally complete and compatible with the current host

## Security and Trust Model

The application trusts only runtime packages that match the expected product format.

First implementation trust rules:

- only zip packages with the required manifest/layout are accepted
- package integrity must be checked using manifest-provided hashes
- the app does not support arbitrary folder import as a first-class path

This reduces the support burden and keeps runtime provenance understandable.

## Verification

Required verification for implementation:

- unit tests for manifest parsing and package layout validation
- unit tests for environment compatibility decisions
- unit tests for staging/activation/rollback behavior with temp directories
- unit tests for settings-window status text and action routing
- unit tests for service-manager behavior after imported runtime activation
- full test suite pass
- Windows runtime verification with at least one supported NVIDIA environment:
  - import a valid runtime zip
  - verify status shows imported runtime metadata
  - start service successfully
  - health check succeeds
  - pronunciation still uses the existing local HTTP path
- negative runtime verification:
  - package with wrong layout is rejected
  - package with mismatched driver requirement is rejected
  - interrupted/failed activation restores the previous runtime

## Out of Scope for the First Cut

- universal single package support for all Windows GPU environments
- remote runtime download and install automation inside the app
- remote/provider-based VoxCPM deployment
- replacing the `voxcpm_local` endpoint contract
- switching away from VoxCPM2
