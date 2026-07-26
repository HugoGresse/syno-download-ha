"""Unit tests for the pure task helpers (no Home Assistant required)."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

HELPERS_PATH = (
    Path(__file__).parent.parent
    / "custom_components"
    / "synology_download_station"
    / "helpers.py"
)
spec = importlib.util.spec_from_file_location("sds_helpers", HELPERS_PATH)
helpers = importlib.util.module_from_spec(spec)
sys.modules["sds_helpers"] = helpers
spec.loader.exec_module(helpers)


def make_task(
    status="downloading",
    size=1000,
    downloaded=500,
    speed_download=100,
    transfer=True,
):
    """Build a stand-in for SynoDownloadTask."""
    additional = {}
    if transfer:
        additional["transfer"] = {
            "size_downloaded": downloaded,
            "speed_download": speed_download,
            "speed_upload": 10,
        }
    return SimpleNamespace(
        id="dbid_1",
        title="ubuntu.iso",
        type="bt",
        status=status,
        size=size,
        additional=additional,
    )


class TestTaskProgress:
    def test_normal(self):
        assert helpers.task_progress(1000, 500) == 50.0

    def test_zero_size_is_unknown(self):
        assert helpers.task_progress(0, 0) is None

    def test_clamped_at_100(self):
        assert helpers.task_progress(1000, 1500) == 100.0

    def test_rounded_one_decimal(self):
        assert helpers.task_progress(3, 1) == 33.3


class TestTaskEta:
    def test_normal(self):
        assert helpers.task_eta(1000, 500, 100) == 5

    def test_no_speed(self):
        assert helpers.task_eta(1000, 500, 0) is None

    def test_done(self):
        assert helpers.task_eta(1000, 1000, 100) is None

    def test_unknown_size(self):
        assert helpers.task_eta(0, 0, 100) is None


class TestTaskToDict:
    def test_full_task(self):
        data = helpers.task_to_dict(make_task())
        assert data["title"] == "ubuntu.iso"
        assert data["progress"] == 50.0
        assert data["speed_download"] == 100
        assert data["eta"] == 5

    def test_missing_transfer_additional(self):
        data = helpers.task_to_dict(make_task(transfer=False))
        assert data["downloaded"] == 0
        assert data["progress"] == 0.0
        assert data["eta"] is None

    def test_additional_raising_keyerror(self):
        class RawTask:
            id = "dbid_2"
            title = "t"
            type = "bt"
            status = "waiting"
            size = 10

            @property
            def additional(self):
                raise KeyError("additional")

        data = helpers.task_to_dict(RawTask())
        assert data["downloaded"] == 0
        assert data["progress"] == 0.0


class TestSummarize:
    def test_empty(self):
        summary = helpers.summarize([])
        assert summary.total == 0
        assert summary.progress is None
        assert summary.tasks == []

    def test_counts_and_weighted_progress(self):
        tasks = [
            helpers.task_to_dict(
                make_task(size=1000, downloaded=1000, status="finished")
            ),
            helpers.task_to_dict(make_task(size=1000, downloaded=250)),
            helpers.task_to_dict(make_task(size=3000, downloaded=750, status="paused")),
            helpers.task_to_dict(make_task(status="seeding")),
            helpers.task_to_dict(make_task(status="error")),
        ]
        summary = helpers.summarize(tasks)
        assert summary.total == 5
        assert summary.downloading == 1
        assert summary.paused == 1
        assert summary.seeding == 1
        assert summary.finished == 1
        assert summary.error == 1
        # (250 + 750) / (1000 + 3000)
        assert summary.progress == 25.0
        # Only in-progress and paused tasks are listed for dashboards.
        assert len(summary.tasks) == 2

    def test_zero_size_tasks_excluded_from_progress(self):
        tasks = [helpers.task_to_dict(make_task(size=0, downloaded=0))]
        summary = helpers.summarize(tasks)
        assert summary.downloading == 1
        assert summary.progress is None
