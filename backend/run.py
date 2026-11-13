"""开发/生产启动入口：``python backend/run.py``。

用法：
    python backend/run.py              # 生产模式（不热更新）
    python backend/run.py --reload     # 开发模式：backend/ 与 generator/ 下 .py 改动自动重启

参数优先级：命令行 > 环境变量（``FB_HOST`` / ``FB_PORT``）> 默认值。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent

# 允许以脚本方式直接运行（backend 目录加入模块搜索路径）；
# uvicorn --reload 的子进程通过 multiprocessing spawn 继承该 sys.path。
sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_HOST = os.environ.get("FB_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("FB_PORT", "8756"))

# 热更新监听目录：后端代码 + 生成器代码。
# 不监听 data/（任务产物、预览缓存会持续写入，监听会导致反复重启）。
RELOAD_DIRS = [str(BACKEND_DIR), str(ROOT / "generator")]


def _patch_windows_reload_restart() -> None:
    """修掉 Windows 下 ``uvicorn --reload`` 的重启卡死问题。

    uvicorn 在 Windows 上通过 ``os.kill(child_pid, signal.CTRL_C_EVENT)`` 让子进程退出：
    这依赖父进程与子进程共享同一个控制台。以「无控制台 + 输出重定向」方式启动时
    （npm 代理脚本、服务化运行、CI 等）没有可投递的 console 事件，子进程收不到 Ctrl+C，
    reloader 会永久阻塞在 ``process.join()``（表现为日志停在 "Reloading..."）。

    这里把重启改为 ``Process.terminate()``（TerminateProcess），不依赖控制台，
    时序仍是「旧子进程退出 -> 新子进程接管父进程已绑定的 socket」。仅在开发模式生效。
    """

    if sys.platform != "win32":
        return

    from uvicorn._subprocess import get_subprocess
    from uvicorn.supervisors import basereload

    def restart(self) -> None:  # type: ignore[no-untyped-def]
        self.is_restarting = True
        try:
            self.process.terminate()
        except Exception:  # pragma: no cover - 子进程可能已经退出
            pass
        self.process.join(timeout=10)
        if self.process.is_alive():  # pragma: no cover - TerminateProcess 失败时兜底
            self.process.kill()
            self.process.join(timeout=5)
        self.process = get_subprocess(
            config=self.config, target=self.target, sockets=self.sockets
        )
        self.process.start()
        # uvicorn 原生实现靠"自己收到的那次 Ctrl+C"把这个标记复位；
        # 我们没用 console 事件，必须显式复位，否则用户第一次 Ctrl+C 会被吞掉。
        self.is_restarting = False

    basereload.BaseReload.restart = restart


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast Building Platform 服务入口")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口（默认 8756）")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="开发模式：监听 backend/ 与 generator/ 下的 .py 文件，改动后自动重启",
    )
    parser.add_argument(
        "--reload-dir",
        action="append",
        default=None,
        metavar="DIR",
        help="额外的热更新监听目录（可重复指定）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    options: dict = {"host": args.host, "port": args.port, "log_level": "info"}
    if args.reload:
        _patch_windows_reload_restart()
        reload_dirs = RELOAD_DIRS + [os.path.abspath(item) for item in (args.reload_dir or [])]
        options.update(
            reload=True,
            reload_dirs=reload_dirs,
            reload_delay=0.5,  # 合并编辑器批量保存，避免连续重建
        )

    uvicorn.run("app.main:app", **options)


if __name__ == "__main__":
    main()
