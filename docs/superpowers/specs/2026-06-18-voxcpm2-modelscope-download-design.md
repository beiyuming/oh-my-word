# VoxCPM2 运行时包 ModelScope 下载与分包导入设计

## 目标

在已有的"导入本地 zip"运行时包流程之上，新增"从 ModelScope 下载"能力，并将运行时和模型拆分为两个独立包，降低单包体积和下载失败率。GitHub Release 只放主安装器和指向 ModelScope 的说明；运行时包和模型包的主源在 ModelScope。

## 已确认的产品决策

1. **双源策略**：ModelScope 为主下载源，GitHub Release 只放主安装器和说明文件。Hugging Face 不作为国内主源。
2. **运行时和模型分包**：运行时 zip 只含 ``.venv``、``service``、脚本；模型单独打包。导入时先下运行时再下模型，拼到一起。
3. **单包 cu130 + 驱动检测**：只发布 ``cu130`` 一个运行时包，应用内检测 NVIDIA 驱动版本，不兼容时明确提示升级驱动或走兜底路径。
4. **下载方式 C**：应用内提供下载按钮，自动从 ModelScope 下载；下载失败时提示用户手动下载再导入。

## 包结构与命名

### 运行时包

不含模型，体积预计几百 MB。

命名：``voxcpm2-runtime-win-x64-cu130-r1.zip``

布局：

```
manifest.json
runtime/
  .venv/
  service/
  start_service.ps1
  healthcheck.ps1
```

``manifest.json`` 在原有字段基础上新增 ``model_package_id`` 和 ``model_package_filename``，用于关联对应的模型包。模型文件不包含在此 zip 中，``runtime/models/`` 目录在运行时包中不存在或为空占位。

### 模型包

只含 VoxCPM2 模型文件，体积约 5GB。

命名：``voxcpm2-model-cu130-r1.zip``

布局：

```
model_manifest.json
models/
  VoxCPM2-local/
    model.safetensors
    config.json
    tokenizer/...
```

``model_manifest.json`` 字段：

- ``model_id``
- ``model_version``
- ``model_package_filename``
- ``expected_model_dir``（固定值 ``VoxCPM2-local``）
- ``package_size``
- ``file_hashes``（覆盖 ``model.safetensors`` 等关键文件）
- ``built_at``

### checksum 文件

每个包配套一个 ``.sha256`` 文件，内容为 ``<hash>  <filename>``。

## ModelScope 托管

### 仓库结构

在 ModelScope 建一个仓库（例如 ``borealis/oh-my-word-voxcpm2-runtime``），上传以下文件：

- ``voxcpm2-runtime-win-x64-cu130-r1.zip``
- ``voxcpm2-runtime-win-x64-cu130-r1.sha256``
- ``voxcpm2-model-cu130-r1.zip``
- ``voxcpm2-model-cu130-r1.sha256``
- ``README.md``（说明环境要求、下载方式、checksum 验证方法）

### 下载 URL

ModelScope 文件下载 URL 格式为：

```
https://modelscope.cn/api/v1/models/{namespace}/{repo}/repo?Revision=master&FilePath={filename}
```

应用内默认值来自 ``app/models.py``，按 filename 拼接下载地址；设置页允许用户直接编辑 namespace、repo、runtime filename 和最低驱动版本，便于后续切换仓库或资产名，而不必改 UI 代码。

## 应用端下载流程

### 入口

设置页"发音"分类中提供四个入口：

- ``下载并导入运行时包``：普通用户首选，顺序下载 runtime zip 和 model zip 并导入
- ``下载并导入模型包``：运行时已就绪后单独补下或重下模型包
- ``导入 VoxCPM 运行时包``：手动下载 runtime zip 后导入
- ``导入模型包``：手动下载 model zip 后导入

同时暴露可编辑的 ``ModelScope 命名空间``、``ModelScope 仓库名``、``运行时包文件名`` 和 ``最低驱动版本`` 字段。点击下载入口后启动以下流程：

### 阶段 1：环境预检

复用已有 ``_probe_runtime_environment()``，检查：

- OS 为 Windows x64
- 存在 NVIDIA GPU
- 驱动版本 >= manifest 声明的 ``min_driver_version``（cu130 对应 580）
- 磁盘剩余空间 >= 运行时包 + 模型包体积之和

不通过时给出具体原因，不开始下载。

### 阶段 2：下载运行时包

- 从 ModelScope 下载 ``voxcpm2-runtime-win-x64-cu130-r1.zip`` 到临时目录
- 下载过程中在 UI 显示进度（按已下载字节数 / Content-Length）
- 下载完成后校验 SHA256 与配套 ``.sha256`` 文件比对
- 校验失败则删除临时文件，提示重试或手动下载

### 阶段 3：导入运行时包

复用已有的 staging 校验、激活、回滚流程：

- 读取 ``manifest.json``
- 校验 zip 布局和文件 hash
- 解压到 staging
- 运行 staging 健康检查
- 激活为活跃运行时

### 阶段 4：下载模型包

运行时激活成功后，自动开始下载模型包：

- 从 ModelScope 下载 ``voxcpm2-model-cu130-r1.zip``
- 同样显示进度和 SHA256 校验
- 校验失败则提示重试或手动下载

### 阶段 5：导入模型包

- 读取 ``model_manifest.json``
- 校验 zip 布局和文件 hash
- 解压到 ``<install_root>/models/``（即 ``tts/voxcpm/models/VoxCPM2-local/``）
- 验证模型文件完整性

### 阶段 6：最终验证

- 启动服务
- 调用 ``/health`` 确认服务正常
- 调用 ``/synthesize`` 或 ``/synthesize_stream`` 确认模型可用
- 通过后刷新设置页状态

### 失败处理

任何阶段失败时：

- 不破坏已有运行时（如果之前有）
- 清理临时下载文件
- 在 UI 显示失败原因和下一步建议
- 提供"手动下载再导入"的替代路径提示，附带 ModelScope 下载地址

## 手动下载兜底路径

设置页同时保留手动导入入口，用户可以：

1. 手动从 ModelScope 下载运行时 zip
2. 点击 ``导入 VoxCPM 运行时包`` 选择文件
3. 应用检测到运行时已导入但模型缺失时，提示用户手动下载模型 zip
4. 提供独立的 ``导入模型包`` 按钮选择模型 zip

## 驱动版本检测

``_probe_runtime_environment()`` 已通过 ``nvidia-smi --query-gpu=driver_version`` 获取驱动版本。``validate_runtime_environment()`` 已有 ``compare_version_parts()`` 比较逻辑。

cu130 运行时包的 ``manifest.json`` 中 ``min_driver_version`` 设为 ``"580"``。不满足时返回明确错误信息：

```
当前 NVIDIA 驱动版本 {actual} 低于运行时要求的 {required}。
请从 NVIDIA 官网升级驱动，或使用系统发音引擎。
```

## 进度反馈

下载过程通过 ``QThread`` + ``Signal`` 回传进度到 UI，避免阻塞主线程。进度信息包括：

- 当前阶段（运行时下载 / 模型下载 / 校验 / 解压 / 健康检查）
- 已下载 / 总字节数
- 百分比

## 下载实现

使用 Python 标准库 ``urllib.request`` 进行 HTTP 下载，不引入额外依赖。支持：

- 流式读取，避免一次性加载大文件到内存
- ``Content-Length`` 头解析总大小
- 超时和重试（最多 3 次，指数退避）
- 断点续传不作为首版目标，但下载失败后保留部分文件以便重试

如果 ModelScope 下载失败，不自动切换到 Hugging Face，而是提示用户手动下载。

## 环境要求文档

设置页和 README 中需明确标注运行时包环境要求：

- Windows 10/11 x64
- NVIDIA GPU，驱动版本 >= 580（支持 CUDA 13.0）
- 推荐 8GB+ VRAM
- 推荐至少 20GB+ 可用磁盘空间（运行时 + 模型 + 临时下载）

## 验证要求

- 单元测试：ModelScope URL 拼接、SHA256 校验、模型包 manifest 解析、模型包布局校验、多阶段导入流程的状态转换
- 单元测试：下载失败重试、校验失败清理、磁盘空间不足拒绝
- 单元测试：驱动版本不兼容时的错误消息
- 完整测试套件通过
- Windows 运行时验证：在本机 cu130 环境执行完整下载导入流程

## 不在首版范围内

- 断点续传
- 自动从 Hugging Face 兜底下载
- 多 CUDA 版本包（cu124 等）
- 应用内自动检查运行时包更新
- 模型包分卷
