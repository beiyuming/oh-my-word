from __future__ import annotations

from app.version import APP_VERSION, CHANGELOG, formatted_changelog


def test_current_version_is_0_1_6() -> None:
    assert APP_VERSION == "0.1.7"


def test_changelog_mentions_versioned_installer_and_streaming_service_update() -> None:
    text = formatted_changelog()

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
    assert CHANGELOG[0].version == "0.1.7"
