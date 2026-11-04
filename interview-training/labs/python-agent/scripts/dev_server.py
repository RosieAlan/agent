"""Local API supervisor: one server, automatic reload, project-scoped cleanup."""

import os
from pathlib import Path
import subprocess
import sys
import time
import msvcrt

import psutil


ROOT = Path(__file__).resolve().parents[1]
PORT = 8000


def stop_tree(process: psutil.Process) -> None:
    """Stop only an identified server and its descendants."""
    try:
        children = process.children(recursive=True)
        processes = [process, *children]
    except psutil.NoSuchProcess:
        return
    for item in processes:
        try:
            item.terminate()
        except psutil.NoSuchProcess:
            pass
    _, remaining = psutil.wait_procs(processes, timeout=3)
    for item in remaining:
        try:
            item.kill()
        except psutil.NoSuchProcess:
            pass
    _, remaining = psutil.wait_procs(remaining, timeout=3)
    if remaining:
        raise RuntimeError("Server processes did not stop; startup aborted")


def clear_old_server() -> None:
    owners = {
        item.pid for item in psutil.net_connections(kind="tcp")
        if item.status == psutil.CONN_LISTEN
        and item.laddr.port == PORT and item.pid
    }
    verified = []
    for pid in owners:
        try:
            process = psutil.Process(pid)
            command = process.cmdline()
            owned = (
                Path(process.cwd()).resolve() == ROOT
                and "uvicorn" in command
                and any(target in command for target in ("app.main:app", "main:app"))
            )
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as error:
            raise RuntimeError(f"Cannot identify port {PORT} owner PID={pid}; startup aborted") from error
        if not owned:
            raise RuntimeError(f"Port {PORT} belongs to another program PID={pid}; left running")
        verified.append(process)
    for process in verified:
        print(f"[dev] Cleaning previous project server PID={process.pid}", flush=True)
        stop_tree(process)


def snapshot() -> tuple:
    # Watch additions, edits and deletions under app; ignore bytecode files.
    return tuple(sorted(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in (ROOT / "app").rglob("*.py") if path.is_file()
    ))


def main() -> int:
    os.chdir(ROOT)
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    with (runtime / "dev.lock").open("a+b") as lock:
        if lock.seek(0, os.SEEK_END) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print("[dev] Project server is already managed. Save app/*.py to reload.", flush=True)
            return 0

        child = None
        try:
            clear_old_server()
            state = snapshot()
            while True:
                if child is None:
                    child = subprocess.Popen([
                        sys.executable, "-u", "-m", "uvicorn", "app.main:app",
                        "--host", "127.0.0.1", "--port", str(PORT),
                    ], cwd=ROOT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                    print(f"[dev] Server PID={child.pid}; save Python files to reload; Ctrl+C to stop.", flush=True)
                time.sleep(0.5)
                current = snapshot()
                if current != state:
                    time.sleep(0.3)  # Combine rapid saves before loading new code.
                    state = snapshot()
                    print("[dev] Python code changed; replacing server...", flush=True)
                    if child.poll() is None:
                        stop_tree(psutil.Process(child.pid))
                    child = None
        except KeyboardInterrupt:
            print("\n[dev] Stopping project server...", flush=True)
            return 0
        except (OSError, RuntimeError, psutil.Error) as error:
            print(f"[dev] {error}", file=sys.stderr, flush=True)
            return 1
        finally:
            if child is not None and child.poll() is None:
                stop_tree(psutil.Process(child.pid))
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    raise SystemExit(main())
