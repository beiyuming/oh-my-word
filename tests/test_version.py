from __future__ import annotations

from app.version import APP_VERSION, CHANGELOG, formatted_changelog


def test_current_version_is_0_1_3() -> None:
    assert APP_VERSION == "0.1.3"


def test_changelog_mentions_versioned_installer_and_streaming_service_update() -> None:
    text = formatted_changelog()

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
    assert CHANGELOG[0].version == "0.1.3"
