from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from filelock import FileLock
from pydantic import BaseModel, Field
from rich.console import Console

from .config_loader import get_project_root, load_tasks_config, load_crew_config
from .crew import ConfigDrivenCrew

console = Console()

SCHEDULES_REL_PATH = Path("db") / "schedules.json"
LOCK_SUFFIX = ".lock"


class ScheduleEntry(BaseModel):
    id: str
    name: str
    crew: Optional[str] = None  # crew name from config/crews.yaml; None = default (first)
    trigger: Literal["date", "interval", "cron"] = "date"
    # date trigger
    run_at: Optional[str] = None  # ISO 8601 datetime string
    # interval trigger
    interval_seconds: Optional[int] = None
    # cron trigger
    cron: Optional[Dict[str, str]] = None  # fields like {minute: "0", hour: "*", ...}
    timezone: Optional[str] = None
    enabled: bool = True
    inputs: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ScheduleStore:
    """File-backed schedule store with a simple file lock for safe writes."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root: Path = (root or get_project_root()).resolve()
        self.path: Path = (self.root / SCHEDULES_REL_PATH).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + LOCK_SUFFIX)

    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"schedules": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            if not isinstance(data, dict):
                return {"schedules": []}
            if not isinstance(data.get("schedules", []), list):
                data["schedules"] = []
            return data
        except Exception:
            return {"schedules": []}

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> List[ScheduleEntry]:
        with self.lock:
            raw = self._read()
            out: List[ScheduleEntry] = []
            for item in raw.get("schedules", []):
                try:
                    out.append(ScheduleEntry.model_validate(item))
                except Exception:
                    continue
            return out

    def upsert(self, entry: ScheduleEntry) -> ScheduleEntry:
        with self.lock:
            data = self._read()
            items: List[Dict[str, Any]] = list(data.get("schedules", []))
            replaced = False
            entry.updated_at = datetime.utcnow().isoformat()
            for i, it in enumerate(items):
                if str(it.get("id")) == entry.id:
                    items[i] = entry.model_dump()
                    replaced = True
                    break
            if not replaced:
                items.append(entry.model_dump())
            data["schedules"] = items
            self._write(data)
            return entry

    def delete(self, schedule_id: str) -> bool:
        with self.lock:
            data = self._read()
            items: List[Dict[str, Any]] = list(data.get("schedules", []))
            new_items = [it for it in items if str(it.get("id")) != schedule_id]
            changed = len(new_items) != len(items)
            if changed:
                data["schedules"] = new_items
                self._write(data)
            return changed


def _precreate_task_output_dirs(root: Path) -> None:
    try:
        tasks_cfg = load_tasks_config(root)
        for _, t_cfg in tasks_cfg.items():
            out = t_cfg.get("output_file")
            if out:
                p = (root / out).resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]Warning: unable to pre-create output directories: {e}[/yellow]")


def _run_crew_job(crew_name: Optional[str], inputs: Dict[str, Any]) -> Tuple[bool, str]:
    root = get_project_root()
    _precreate_task_output_dirs(root)
    try:
        crew_cfg = load_crew_config(root, crew_name)
        instance = ConfigDrivenCrew(crew_name=crew_name)
        # For scheduled jobs, run synchronously to simplify lifecycle
        result = instance.crew().kickoff(inputs=inputs or {"topic": "Hello World"})
        return True, str(result)
    except Exception as e:  # noqa: BLE001
        import traceback
        return False, traceback.format_exc()


class SchedulerService:
    """APScheduler-based service that loads jobs from the file store and runs crews.

    It watches the schedules.json file for changes (mtime polling) and updates jobs accordingly.
    """

    def __init__(self, root: Optional[Path] = None, poll_seconds: int = 5) -> None:
        self.root = (root or get_project_root()).resolve()
        self.store = ScheduleStore(self.root)
        self.scheduler = BackgroundScheduler()
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._known_versions: Dict[str, str] = {}  # id -> updated_at
        self._file_mtime: float = 0.0

    def _build_trigger(self, entry: ScheduleEntry):
        if entry.trigger == "date":
            if not entry.run_at:
                raise ValueError("date trigger requires run_at")
            dt = datetime.fromisoformat(entry.run_at)
            return DateTrigger(run_date=dt)
        if entry.trigger == "interval":
            if not entry.interval_seconds or entry.interval_seconds <= 0:
                raise ValueError("interval trigger requires positive interval_seconds")
            return IntervalTrigger(seconds=int(entry.interval_seconds))
        if entry.trigger == "cron":
            if not entry.cron or not isinstance(entry.cron, dict):
                raise ValueError("cron trigger requires cron field mapping")
            return CronTrigger(**{k: v for k, v in entry.cron.items() if v is not None})
        raise ValueError(f"Unsupported trigger: {entry.trigger}")

    def _job_func(self, schedule_id: str, crew_name: Optional[str], inputs: Dict[str, Any]) -> None:
        ok, out = _run_crew_job(crew_name, inputs)
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        log_dir = (self.root / "output" / "run-logs").resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"schedule_{schedule_id}_{ts}.log"
        header = f"[schedule {schedule_id}] {datetime.utcnow().isoformat()}\n"
        try:
            log_file.write_text(header + (out or ""), encoding="utf-8")
        except Exception:
            pass
        if ok:
            console.print(f"[green]Schedule {schedule_id} run completed.[/green]")
        else:
            console.print(f"[red]Schedule {schedule_id} run failed. See log {log_file}[/red]")

    def _sync_jobs_from_store(self) -> None:
        entries = self.store.list()
        current_ids = {e.id for e in entries if e.enabled}
        # remove jobs that no longer exist or are disabled
        for job in list(self.scheduler.get_jobs()):
            if job.id not in current_ids:
                self.scheduler.remove_job(job.id)
        # add/update enabled jobs
        for e in entries:
            if not e.enabled:
                continue
            try:
                trigger = self._build_trigger(e)
            except Exception as err:
                console.print(f"[yellow]Skipping schedule {e.id}: invalid trigger ({err})[/yellow]")
                continue
            needs_update = self._known_versions.get(e.id) != e.updated_at
            if not needs_update and self.scheduler.get_job(e.id):
                continue
            # remove if exists then add
            if self.scheduler.get_job(e.id):
                self.scheduler.remove_job(e.id)
            self.scheduler.add_job(
                id=e.id,
                func=self._job_func,
                trigger=trigger,
                args=[e.id, e.crew, e.inputs or {}],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            self._known_versions[e.id] = e.updated_at

    def _watch_loop(self) -> None:
        schedules_path = self.store.path
        while not self._stop.is_set():
            try:
                mtime = schedules_path.stat().st_mtime if schedules_path.exists() else 0.0
                if mtime != self._file_mtime:
                    self._file_mtime = mtime
                    self._sync_jobs_from_store()
            except Exception:
                pass
            finally:
                self._stop.wait(self.poll_seconds)

    def run_forever(self) -> None:
        console.rule("Scheduler Service")
        console.print(f"Root: {self.root}")
        console.print(f"Store: {self.store.path}")
        self.scheduler.start()
        # Initial sync
        self._sync_jobs_from_store()
        # Watcher thread
        watcher = threading.Thread(target=self._watch_loop, name="schedules-watcher", daemon=True)
        watcher.start()
        console.print("[green]Scheduler is running. Press Ctrl+C to stop.[/green]")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            console.print("Stopping scheduler...")
        finally:
            self._stop.set()
            self.scheduler.shutdown(wait=False)


# Convenience helpers for CLI/Tools

def list_schedules(root: Optional[Path] = None) -> List[ScheduleEntry]:
    return ScheduleStore(root).list()


def upsert_schedule(entry: ScheduleEntry, root: Optional[Path] = None) -> ScheduleEntry:
    return ScheduleStore(root).upsert(entry)


def delete_schedule(schedule_id: str, root: Optional[Path] = None) -> bool:
    return ScheduleStore(root).delete(schedule_id)
