from __future__ import annotations

from dataclasses import dataclass


APP_VERSION = "0.1.19"


@dataclass(slots=True, frozen=True)
class ChangelogEntry:
    version: str
    date: str
    changes: tuple[str, ...]


CHANGELOG: tuple[ChangelogEntry, ...] = (
    ChangelogEntry(
        version="0.1.19",
        date="2026-06-23",
        changes=(
            "设置页发音分类新增默认折叠的 VoxCPM 高级参数区域，可持久化设备、optimize、CFG、推理步数、badcase 重试和首尾静音参数。",
            "VoxCPM 流式播放新增预缓冲最大等待时间和首字节、预缓冲、生成倍率等诊断日志，旧 service 404/405 时会明确记录并回退完整 WAV。",
            "设置窗口改为小屏幕友好的滚动布局，限制初始尺寸并允许缩小，避免长路径、说明和按钮组撑破窗口。",
        ),
    ),
    ChangelogEntry(
        version="0.1.18",
        date="2026-06-20",
        changes=(
            "修复应用内 ModelScope 下载地址仍指向旧 api/v1 形态，现已切换到真实可下载的 resolve/master 资产地址。",
            "修复运行时包/模型包 blocking 下载 helper 用消息文本误判成功的问题，失败分支现在会准确返回 False。",
            "补齐 ModelScope runtime/model 下载成功请求序列与 runtime zip、runtime sha、model zip、model sha 失败路径测试，并同步更新下载设计文档。",
        ),
    ),
    ChangelogEntry(
        version="0.1.17",
        date="2026-06-20",
        changes=(
            "修复 Windows 上导入 VoxCPM 运行时包或模型包时，目录激活阶段偶发 WinError 5 拒绝访问导致导入失败的问题。",
            "运行时目录和模型目录现在会优先使用 rename 激活，若命中 PermissionError 则自动回退到 shutil.move。",
            "已用真实魔搭 r2 运行时包和模型包完成隔离端到端验证，确认导入后可启动本地服务并通过 /health 检查。",
        ),
    ),
    ChangelogEntry(
        version="0.1.16",
        date="2026-06-19",
        changes=(
            "VoxCPM2 预构建运行时包改为自包含 portable Python 布局，不再依赖目标机器预装 Python。",
            "应用导入与启动逻辑已同时兼容新的 runtime\\python\\python.exe 布局和旧的 .venv 布局。",
            "默认下载入口已切换到新的 voxcpm2-runtime-win-x64-cu130-r2.zip / voxcpm2-model-cu130-r2.zip 资产。",
        ),
    ),
    ChangelogEntry(
        version="0.1.15",
        date="2026-06-18",
        changes=(
            "设置页手动导入 VoxCPM 运行时包和模型包已改为后台线程执行，不再把 ZIP 校验、清理、解压和自检堵在 UI 线程。",
            "导入期间状态区会显示校验、清理残留、解压、自检和激活阶段提示，并临时禁用重复点击按钮。",
            "后台导入或下载结束后，托盘会补发最终成功/失败结果，便于确认任务是否完成。",
        ),
    ),

    ChangelogEntry(
        version="0.1.14",
        date="2026-06-18",
        changes=(
            "修复导入运行时包时直接执行 /health 导致的误报；现在改为用运行时 Python 自检导入 service 模块。",
            "导入预构建运行时包后，会重写 start_service.ps1 和 healthcheck.ps1，去掉构建机硬编码路径。",
            "修复导入后本地服务仍可能指向错误模型目录或错误端口的问题。",
        ),
    ),
    ChangelogEntry(
        version="0.1.13",
        date="2026-06-18",
        changes=(
            "设置页新增“下载并导入模型包”，运行时已安装后可以单独补下或重下模型包。",
            "设置页已接通可编辑的 ModelScope 路径字段，运行时/模型下载统一读取当前设置值。",
            "安装器移除旧的 VoxCPM 下载/安装入口，只保留主程序安装，VoxCPM2 改为应用内下载或导入。",
        ),
    ),
    ChangelogEntry(
        version="0.1.12",
        date="2026-06-18",
        changes=(
            "移除旧的「后台安装 / 更新」入口，用户统一使用 ModelScope 运行时包导入流程。",
            "设置页 VoxCPM 操作按钮改为两行布局，避免窄窗口按钮被裁切。",
            "修复下载并导入运行时包未使用设置中 ModelScope 路径的问题。",
        ),
    ),
    ChangelogEntry(
        version="0.1.11",
        date="2026-06-18",
        changes=(
            "VoxCPM 运行时包下载路径（ModelScope 命名空间/仓库名/文件名/驱动版本）改为可在设置页直接修改。",
            "ModelScope 下载仓库已从 bei_yu_ming 切换为 borealis，运行时包与模型包已上传。",
        ),
    ),
    ChangelogEntry(
        version="0.1.10",
        date="2026-06-18",
        changes=(
            "设置页新增“导入 VoxCPM 运行时包”，普通用户现在可以直接导入 GitHub Release 发布的预构建 VoxCPM2 runtime zip。",
            "VoxCPM 运行时状态区会显示 runtime ID、CUDA 标签、最低驱动要求和模型版本，便于确认当前机器与运行时矩阵是否匹配。",
            "README 和稳定 spec 已改为以运行时包为首选路径，明确 Windows 10/11 x64、NVIDIA GPU、8 GB+ VRAM 和 15 GB+ 磁盘空间建议。",
        ),
    ),
    ChangelogEntry(
        version="0.1.9",
        date="2026-06-17",
        changes=(
            "VoxCPM 本地安装脚本在某个 Python 运行时无法创建 venv 时，会自动清理残留目录并继续尝试下一个兼容解释器。",
            "VoxCPM 安装日志现在会明确记录每个 Python 候选创建虚拟环境的失败原因，便于定位目标机器上的环境问题。",
            "VoxCPM 安装脚本现在允许 python/python3 这类无额外参数的运行时候选正常探测，不再因空参数数组触发 PowerShell 参数绑定错误。",
            "VoxCPM 安装脚本返回的 Python 候选列表已改为扁平数组，避免多解释器环境下把数组对象误传给 Invoke-Native -FilePath。",
        ),
    ),
    ChangelogEntry(
        version="0.1.8",
        date="2026-06-17",
        changes=(
            "VoxCPM 本地朗读改为 Qt 官方异步网络和音频播放链路，不再在主线程里阻塞等待 HTTP 响应或音频流。",
            "点击朗读时不再先同步探测 /health；自动启动本地服务后，会等真正开始播放再记录 last_pronounced_at。",
            "VoxCPM 异步播放失败现在会回传托盘提示，减少点击后调度前进但实际未播出的假成功状态。",
        ),
    ),
    ChangelogEntry(
        version="0.1.7",
        date="2026-06-14",
        changes=(
            "VoxCPM 可选安装现在会自动探测可用的 Python 运行时，不再只依赖 py -3.11；找不到合适解释器时会给出更明确的错误。",
            "安装器里 VoxCPM 模型目录输入框的事件绑定顺序已修正，避免窗体初始化时触发空引用。",
            "设置页“检查服务”会先应用当前打开窗口里的 VoxCPM 路径和镜像设置，再去查询服务状态。",
        ),
    ),
    ChangelogEntry(
        version="0.1.6",
        date="2026-06-14",
        changes=(
            "VoxCPM 默认安装位置调整为主程序目录下的 tts\\voxcpm，模型默认放在 tts\\voxcpm\\models。",
            "安装器中修改主程序安装目录时，会同步更新未手动改过的 VoxCPM engine 和模型目录。",
            "保留 VoxCPM 可选安装边界，安装包仍只内置 service-only 文件，不携带模型、venv 或 Torch/CUDA 依赖。",
        ),
    ),
    ChangelogEntry(
        version="0.1.5",
        date="2026-06-14",
        changes=(
            "设置页发音分类新增 VoxCPM 流式预缓冲时间，可在 0.00 到 2.00 秒之间调整并保存后立即生效。",
            "VoxCPM 流式播放会按用户设置先预缓冲 PCM 音频，再启动播放，以降低句中 underflow 卡顿。",
            "VoxCPM 单词加例句朗读去掉双换行强停顿，改为轻停顿空格，减少句中停顿感。",
        ),
    ),
    ChangelogEntry(
        version="0.1.4",
        date="2026-06-14",
        changes=(
            "VoxCPM 本地发音新增可自定义的语气提示词，按 VoxCPM Voice Design 格式应用到合成文本。",
            "VoxCPM 朗读单词时会为单词加英文引号并保留停顿，降低短词首尾偶发漏读的概率。",
        ),
    ),
    ChangelogEntry(
        version="0.1.3",
        date="2026-06-13",
        changes=(
            "修复设置页停止 VoxCPM 服务后，旧服务仍占用端口导致检测又显示运行中的问题。",
            "停止服务现在会识别并停止同一 endpoint 上的 VoxCPM uvicorn 旧服务进程，同时避免误杀无关进程。",
        ),
    ),
    ChangelogEntry(
        version="0.1.2",
        date="2026-06-13",
        changes=(
            "VoxCPM 本地服务显式启用官方 badcase 重试参数，减少过短音频导致的首尾漏读。",
            "VoxCPM 默认 cfg_value 降为 1.5，并支持通过环境变量继续微调生成稳定性。",
            "VoxCPM 流式和完整 WAV 输出都增加短首尾静音垫，降低声卡播放起音/尾音被截断的概率。",
        ),
    ),
    ChangelogEntry(
        version="0.1.1",
        date="2026-06-13",
        changes=(
            "安装包文件名带版本号，当前版本为 v0.1.1。",
            "设置页新增关于/更新日志，显示当前版本和每次更新内容。",
            "VoxCPM 本地服务安装/更新时强制刷新 service 文件，并校验流式接口文件已复制。",
            "选词从字母序固定弹出改为同一候选池内按待学习力加权随机。",
        ),
    ),
)


def formatted_changelog() -> str:
    sections = ["更新日志"]
    for entry in CHANGELOG:
        sections.append(f"v{entry.version} - {entry.date}")
        sections.extend(f"- {change}" for change in entry.changes)
    return "\n".join(sections)

