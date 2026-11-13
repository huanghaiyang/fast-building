"""批量渲染街市风格的多视角 QA 图。

用法（在仓库根目录）：
    powershell -File tools/qa_styles.ps1   # 见同名脚本
本脚本只被 QA 流程调用：逐个风格跑 tools/render_style.py，产物落在 .run/qa/<风格>/。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = r"D:\blender\blender.exe"
STYLES = [
    "watermill_house",
    "village_bookshop",
    "general_store",
    "storage_barn",
    "stable_barn",
]


def main() -> int:
    views = sys.argv[1] if len(sys.argv) > 1 else "front,quarter,side"
    res = sys.argv[2] if len(sys.argv) > 2 else "900"
    for style in STYLES:
        out = ROOT / ".run" / "qa" / style
        cmd = [
            BLENDER,
            "-b",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tools" / "render_style.py"),
            "--",
            "--style",
            style,
            "--out",
            str(out),
            "--views",
            views,
            "--res",
            res,
        ]
        print("@@RUN", style, flush=True)
        completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in (completed.stdout or "").splitlines():
            if line.startswith("@@VIEW") or line.startswith("@@STATS"):
                print(line, flush=True)
        if completed.returncode != 0:
            print("@@FAIL", style, (completed.stderr or "")[-1200:], flush=True)
            return completed.returncode
    print("@@ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
