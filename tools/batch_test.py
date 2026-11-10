"""批量稳定性测试：连续生成 20 栋随机建筑并统计耗时。

运行：
    D:\\thirdparty\\venvs\\fastbuild\\Scripts\\python.exe tools\\batch_test.py

产物位于 data/jobs/_batch/<index>/out/model.glb，便于事后抽查。
"""

from __future__ import annotations

import json
import random
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"D:\blender\blender.exe")
ENTRY = ROOT / "generator" / "entry.py"
BATCH_DIR = ROOT / "data" / "jobs" / "_batch"

STYLES = ["modern_villa", "townhouse", "office", "cottage"]
TEXTURES = ["brick_red", "concrete_gray", "roof_tile"]


def make_spec(index: int) -> dict:
    rng = random.Random(1000 + index)
    return {
        "width": rng.choice([9, 10.5, 12, 15, 18, 21]),
        "depth": rng.choice([7.5, 9, 10.5, 12, 15]),
        "bays": rng.randint(1, 5),
        "floors": rng.randint(1, 5),
        "floor_height": rng.choice([2.8, 3.0, 3.3, 3.6]),
        "roof": rng.choice(["flat", "gable"]),
        "roof_pitch": rng.randint(15, 45),
        "style": rng.choice(STYLES),
        "textureset": rng.choice(TEXTURES),
        "lod": 0,
        "seed": rng.randint(1, 9999),
        "balcony": rng.choice([True, False]),
        "openings": {
            "window_w": rng.choice([1.1, 1.4, 1.7]),
            "window_h": rng.choice([1.3, 1.6, 1.9]),
            "sill_h": rng.choice([0.7, 0.9, 1.0]),
            "door_w": 1.05,
            "door_h": 2.2,
        },
    }


def run_one(index: int) -> tuple[bool, float, str]:
    job_dir = BATCH_DIR / f"{index:02d}"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)
    job_file = job_dir / "in.json"
    job_file.write_text(json.dumps(make_spec(index), ensure_ascii=False, indent=2), encoding="utf-8")

    command = [
        str(BLENDER),
        "-b",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(ENTRY),
        "--",
        "--job",
        str(job_file),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(job_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    elapsed = time.perf_counter() - started
    glb = job_dir / "out" / "model.glb"
    ok = completed.returncode == 0 and glb.exists() and glb.stat().st_size > 20_000
    detail = "" if ok else (completed.stdout or "")[-600:] + (completed.stderr or "")[-400:]
    return ok, elapsed, detail


def main() -> int:
    if not BLENDER.exists():
        print(f"未找到 Blender: {BLENDER}")
        return 2

    count = 20
    times: list[float] = []
    failures = 0
    for index in range(count):
        try:
            ok, elapsed, detail = run_one(index)
        except subprocess.TimeoutExpired:
            failures += 1
            print(f"[{index:02d}] TIMEOUT")
            continue
        times.append(elapsed)
        if not ok:
            failures += 1
        print(f"[{index:02d}] {'PASS' if ok else 'FAIL'} {elapsed:.2f}s")
        if detail:
            print(detail)

    if not times:
        print("没有成功样本")
        return 1

    times.sort()
    p50 = statistics.median(times)
    p95 = times[min(len(times) - 1, int(len(times) * 0.95))]
    print(
        f"\n样本 {len(times)} / 失败 {failures} | "
        f"平均 {statistics.mean(times):.2f}s | P50 {p50:.2f}s | P95 {p95:.2f}s | 最大 {max(times):.2f}s"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
