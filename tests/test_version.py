from __future__ import annotations

from app.version import APP_VERSION, CHANGELOG, formatted_changelog


def test_current_version_is_0_1_18() -> None:
    assert APP_VERSION == "0.1.18"


def test_changelog_mentions_current_and_prior_updates() -> None:
    text = formatted_changelog()

    assert "v0.1.18" in text
    assert "resolve/master" in text
    assert "api/v1" in text
    assert "False" in text
    assert "runtime zip、runtime sha、model zip、model sha" in text
    assert "v0.1.17" in text
    assert "WinError 5" in text
    assert "shutil.move" in text
    assert "/health" in text
    assert "v0.1.16" in text
    assert "portable Python" in text
    assert "runtime\\python\\python.exe" in text
    assert "voxcpm2-runtime-win-x64-cu130-r2.zip" in text
    assert "v0.1.15" in text
    assert "后台线程执行" in text
    assert "校验、清理残留、解压、自检和激活阶段提示" in text
    assert "托盘会补发最终成功/失败结果" in text
    assert "v0.1.14" in text
    assert "直接执行 /health 导致的误报" in text
    assert "重写 start_service.ps1 和 healthcheck.ps1" in text
    assert "错误模型目录或错误端口" in text
    assert "v0.1.13" in text
    assert "v0.1.12" in text
    assert "v0.1.9" in text
    assert "无法创建 venv" in text
    assert "失败原因" in text
    assert "空参数数组" in text
    assert "扁平数组" in text
    assert "v0.1.8" in text
    assert "Qt 官方异步网络和音频播放链路" in text
    assert "同步探测 /health" in text
    assert "last_pronounced_at" in text
    assert "异步播放失败" in text
    assert "v0.1.7" in text
    assert "自动探测可用的 Python 运行时" in text
    assert "空引用" in text
    assert "检查服务" in text
    assert "tts\\voxcpm" in text
    assert "service-only" in text
    assert "v0.1.5" in text
    assert "流式预缓冲" in text
    assert "卡顿" in text
    assert "v0.1.4" in text
    assert "语气提示词" in text
    assert "引号" in text
    assert "v0.1.3" in text
    assert "停止服务" in text
    assert "旧服务" in text
    assert "v0.1.2" in text
    assert "VoxCPM" in text
    assert "首尾" in text
    assert "badcase" in text
    assert "v0.1.1" in text
    assert "安装包文件名带版本号" in text
    assert "VoxCPM" in text
    assert "流式" in text
    assert CHANGELOG[0].version == "0.1.18"
