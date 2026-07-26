"""Pure helpers to normalize Download Station task data.

This module must stay free of Home Assistant imports so it can be
unit-tested without a running hass instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

IN_PROGRESS_STATES = frozenset(
    {
        "downloading",
        "waiting",
        "finishing",
        "hash_checking",
        "extracting",
        "filehosting_waiting",
    }
)
PAUSED_STATE = "paused"
SEEDING_STATE = "seeding"
FINISHED_STATE = "finished"
ERROR_STATE = "error"


@dataclass(slots=True)
class DownloadSummary:
    """Aggregated view of all Download Station tasks."""

    downloading: int = 0
    paused: int = 0
    seeding: int = 0
    finished: int = 0
    error: int = 0
    total: int = 0
    progress: float | None = None
    latest_completed: dict[str, Any] | None = None
    tasks: list[dict[str, Any]] = field(default_factory=list)


def task_progress(size: int, downloaded: int) -> float | None:
    """Return completion percent, or None when the size is unknown."""
    if size <= 0:
        return None
    return round(min(downloaded / size, 1.0) * 100, 1)


def task_eta(size: int, downloaded: int, speed: int) -> int | None:
    """Return remaining seconds at the current speed, or None."""
    if size <= 0 or speed <= 0 or downloaded >= size:
        return None
    return round((size - downloaded) / speed)


def task_to_dict(task: Any) -> dict[str, Any]:
    """Flatten a SynoDownloadTask into a template-friendly dict."""
    try:
        additional = task.additional or {}
    except KeyError:
        additional = {}
    transfer = additional.get("transfer") or {}
    detail = additional.get("detail") or {}
    downloaded = transfer.get("size_downloaded", 0)
    speed_download = transfer.get("speed_download", 0)
    return {
        "id": task.id,
        "title": task.title,
        "type": task.type,
        "status": task.status,
        "size": task.size,
        "downloaded": downloaded,
        "speed_download": speed_download,
        "speed_upload": transfer.get("speed_upload", 0),
        "progress": task_progress(task.size, downloaded),
        "eta": task_eta(task.size, downloaded, speed_download),
        "completed_time": detail.get("completed_time", 0),
    }


def summarize(tasks: list[dict[str, Any]]) -> DownloadSummary:
    """Aggregate task dicts into counters and an overall progress percent.

    Overall progress is size-weighted across in-progress and paused tasks,
    None when nothing is queued.
    """
    summary = DownloadSummary(total=len(tasks))
    size_sum = 0
    downloaded_sum = 0
    latest: dict[str, Any] | None = None
    for task in tasks:
        status = task["status"]
        if status in IN_PROGRESS_STATES:
            summary.downloading += 1
        elif status == PAUSED_STATE:
            summary.paused += 1
        elif status == SEEDING_STATE:
            summary.seeding += 1
        elif status == FINISHED_STATE:
            summary.finished += 1
        elif status == ERROR_STATE:
            summary.error += 1
        if status in IN_PROGRESS_STATES or status == PAUSED_STATE:
            summary.tasks.append(task)
            if task["size"] > 0:
                size_sum += task["size"]
                downloaded_sum += task["downloaded"]
        # Seeding tasks have finished downloading too; ">=" keeps the later
        # list entry as a fallback ordering when completed_time is missing.
        if status in (FINISHED_STATE, SEEDING_STATE) and (
            latest is None
            or task.get("completed_time", 0) >= latest.get("completed_time", 0)
        ):
            latest = task
    if latest is not None:
        summary.latest_completed = {
            "title": latest["title"],
            "size": latest["size"],
            "completed_time": latest.get("completed_time", 0),
        }
    if size_sum:
        summary.progress = round(downloaded_sum / size_sum * 100, 1)
    return summary
