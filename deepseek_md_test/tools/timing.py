import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "output" / "report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
STEPS_FILE = REPORT_DIR / "steps.jsonl"


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class StepRecorder:
    """记录一个 step 的开始/完成时间、耗时、状态、元数据。"""

    def __init__(self, name: str, meta: dict | None = None):
        self.name = name
        self.meta = meta or {}
        self.started_at = None
        self.finished_at = None
        self.status = "unknown"
        self.error = None
        self.extra = {}

    def __enter__(self):
        self.started_at = now_iso()
        self._t0 = time.time()
        print(f"[{self.started_at}] STEP START: {self.name}")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finished_at = now_iso()
        self.duration_sec = round(time.time() - self._t0, 3)

        if exc_type is None:
            self.status = "ok"
        else:
            self.status = "error"
            self.error = f"{exc_type.__name__}: {exc}"

        record = {
            "step": self.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_sec": self.duration_sec,
            "status": self.status,
            "error": self.error,
            "meta": self.meta,
            "extra": self.extra,
        }

        with STEPS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"[{self.finished_at}] STEP END:   {self.name} "
              f"({self.duration_sec}s, {self.status})")

        # 不吞异常，让它继续往上抛
        return False