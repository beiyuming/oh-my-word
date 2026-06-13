from __future__ import annotations

from dataclasses import dataclass


APP_VERSION = "0.1.3"


@dataclass(slots=True, frozen=True)
class ChangelogEntry:
    version: str
    date: str
    changes: tuple[str, ...]


CHANGELOG: tuple[ChangelogEntry, ...] = (
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
