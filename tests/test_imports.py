"""Smoke test: every module imports against the installed Home Assistant."""

import pytest

pytest.importorskip("homeassistant")


def test_all_modules_import():
    from custom_components.synology_download_station import (  # noqa: F401
        config_flow,
        const,
        coordinator,
        entity,
        helpers,
        sensor,
        services,
        text,
    )

    assert const.DOMAIN == "synology_download_station"
    assert len(sensor.SENSORS) == 5
