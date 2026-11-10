"""建筑生成任务的排队与 Blender 子进程调度。

设计要点：
- 任务串行执行：Blender 冷启动本身就要数秒，串行可以避免内存/显卡争抢。
- 所有任务状态都会落盘到 ``data/jobs/<id>/job.json``，服务重启后仍可查询历史。
- 与 Blender 之间通过 stdout 标记行通信（``@@STAGE`` / ``@@DONE`` 等），
  避免引入额外 IPC 依赖，同时日志对用户可读。
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..config import BLENDER_EXE, GENERATOR_ENTRY, JOB_TIMEOUT_SECONDS, JOBS_DIR

# Windows 下隐藏 Blender 控制台窗口
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Job:
    id: str
    status: str = "queued"
    stage: str = "排队中"
    progress: float = 0.0
    logs: list[str] = field(default_factory=list)
    error: str | None = None
    result: dict = field(default_factory=lambda: {"glb": None, "meta": None, "stats": {}})
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    spec: dict = field(default_factory=dict)

    @property
    def dir(self) -> Path:
        return JOBS_DIR / self.id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "stage": self.stage,
            "progress": round(float(self.progress), 4),
            "logs": self.logs[-400:],
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "spec": self.spec,
        }

    def persist(self) -> None:
        self.updated_at = _now()
        target = self.dir / "job.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)


class JobManager:
    """内存任务表 + 单工作线程。"""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._worker = threading.Thread(target=self._loop, name="blender-worker", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------ 对外接口
    def submit(self, spec: dict) -> Job:
        job_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        job = Job(id=job_id, spec=spec)
        job.dir.mkdir(parents=True, exist_ok=True)
        (job.dir / "in.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with self._lock:
            self._jobs[job_id] = job
        job.persist()
        self._queue.put(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None:
            return job
        # 服务重启后的兜底：从磁盘恢复只读视图
        state_file = JOBS_DIR / job_id / "job.json"
        if not state_file.exists():
            return None
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        job = Job(id=data.get("id", job_id))
        job.status = data.get("status", "failed")
        job.stage = data.get("stage", "")
        job.progress = float(data.get("progress", 0))
        job.logs = list(data.get("logs", []))
        job.error = data.get("error")
        job.result = data.get("result") or {"glb": None, "meta": None, "stats": {}}
        job.created_at = data.get("created_at", "")
        job.updated_at = data.get("updated_at", "")
        job.spec = data.get("spec", {})
        return job

    def list(self, limit: int = 20) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.status not in ("queued", "running"):
            return False
        job.status = "canceled"
        job.stage = "已取消"
        job.persist()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            _kill_tree(proc.pid)
        return True

    # ------------------------------------------------------------------ 内部实现
    def _loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._run(job_id)
            except Exception as exc:  # pragma: no cover - 防御性兜底
                job = self.get(job_id)
                if job is not None:
                    job.status = "failed"
                    job.error = f"调度异常: {exc}"
                    job.persist()
            finally:
                self._queue.task_done()

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None or job.status == "canceled":
            return

        job.status = "running"
        job.stage = "启动 Blender"
        job.progress = 0.02
        job.logs = [f"[{_now()}] 使用 {BLENDER_EXE}"]
        job.persist()

        if not BLENDER_EXE.exists():
            job.status = "failed"
            job.error = f"未找到 Blender 可执行文件：{BLENDER_EXE}"
            job.persist()
            return
        if not job.dir.joinpath("in.json").exists():
            job.status = "failed"
            job.error = "任务输入 in.json 缺失"
            job.persist()
            return

        cmd = [
            str(BLENDER_EXE),
            "-b",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(GENERATOR_ENTRY),
            "--",
            "--job",
            str(job.dir / "in.json"),
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        log_path = job.dir / "log.txt"
        timed_out = threading.Event()

        def _timeout_kill() -> None:
            timed_out.set()
            if self._proc is not None and self._proc.poll() is None:
                _kill_tree(self._proc.pid)

        with log_path.open("w", encoding="utf-8") as log_file:
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=str(job.dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    creationflags=CREATE_NO_WINDOW,
                )
            except OSError as exc:
                job.status = "failed"
                job.error = f"启动 Blender 失败: {exc}"
                job.persist()
                return

            timer = threading.Timer(JOB_TIMEOUT_SECONDS, _timeout_kill)
            timer.daemon = True
            timer.start()

            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                line = line.rstrip("\r\n")
                if not line:
                    continue
                log_file.write(line + "\n")
                log_file.flush()
                self._consume_line(job, line)

            try:
                return_code = self._proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                _kill_tree(self._proc.pid)
                return_code = -1
            timer.cancel()
            self._proc = None

        if job.status == "canceled":
            job.stage = "已取消"
            job.persist()
            return

        if timed_out.is_set():
            job.status = "failed"
            job.error = f"生成超时（>{JOB_TIMEOUT_SECONDS}s），已终止 Blender"
            job.persist()
            return

        glb_path = job.dir / "out" / "model.glb"
        if return_code == 0 and glb_path.exists():
            job.status = "succeeded"
            job.stage = "完成"
            job.progress = 1.0
            job.result["glb"] = f"/out/{job.id}/out/model.glb"
            job.result["meta"] = f"/out/{job.id}/out/meta.json"
            job.result["stats"] = _read_stats(job.dir / "out" / "meta.json", job.result.get("stats") or {})
            job.logs.append(f"[{_now()}] 生成成功：{glb_path.name}（{glb_path.stat().st_size / 1024:.1f} KB）")
        else:
            job.status = "failed"
            job.error = _tail_error(job.logs) or f"Blender 退出码 {return_code}"
            job.stage = "失败"
        job.persist()

    # ------------------------------------------------------------------ 日志协议
    def _consume_line(self, job: Job, line: str) -> None:
        if line.startswith("@@"):
            parts = line.split(" ", 2)
            marker = parts[0][2:]
            if marker == "STAGE" and len(parts) >= 3:
                job.stage = _stage_label(parts[1])
                try:
                    job.progress = max(job.progress, min(float(parts[2]), 0.99))
                except ValueError:
                    pass
                job.persist()
                return
            if marker == "STATS" and len(parts) >= 2:
                try:
                    stats = json.loads(parts[1] if len(parts) == 2 else line[8:])
                    job.result.setdefault("stats", {}).update(stats)
                except json.JSONDecodeError:
                    pass
                return
            if marker == "DONE":
                job.stage = "导出完成"
                job.progress = 0.99
                job.persist()
                return
            if marker == "ERROR" and len(parts) >= 2:
                job.error = line[8:]
                return
        job.logs.append(line)
        if len(job.logs) > 600:
            job.logs = job.logs[-400:]


_STAGE_LABELS = {
    "init": "初始化场景",
    "styles": "读取风格预设",
    "modules": "装配模块",
    "walls": "生成墙体与门窗",
    "slabs": "生成楼板",
    "stairs": "生成楼梯",
    "roof": "生成屋顶",
    "materials": "构建 PBR 材质",
    "export": "导出 GLB",
}


def _stage_label(stage: str) -> str:
    return _STAGE_LABELS.get(stage, stage)


def _kill_tree(pid: int) -> None:
    """结束 Blender 进程树（Windows 下 blender 会派生子进程）。"""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
            )
        else:  # pragma: no cover
            os.kill(pid, 9)
    except OSError:
        pass


def _read_stats(meta_path: Path, fallback: dict) -> dict:
    if not meta_path.exists():
        return fallback
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    stats = dict(fallback)
    stats.update(meta.get("stats") or {})
    return stats


def _tail_error(logs: list[str]) -> str | None:
    for line in reversed(logs[-80:]):
        low = line.lower()
        if "error" in low or "traceback" in low or line.startswith("@@ERROR"):
            return line.replace("@@ERROR ", "")[:400]
    return None


manager = JobManager()
