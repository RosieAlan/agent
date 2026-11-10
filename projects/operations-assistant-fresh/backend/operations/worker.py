"""运行：python -m operations.worker；单轮检查：python -m operations.worker --once。"""
import argparse
import logging
import os
import signal
import threading
from uuid import uuid4

from . import repository as repo

logger = logging.getLogger('operations.worker')


def tick(worker_id):
    run = repo.claim(worker_id)
    if run is None:
        return False
    try:
        if repo.complete(run['id'], worker_id):
            logger.info('run_completed id=%s', run['id'])
    except Exception:
        # 数据库错误正文可能包含连接参数，仅记录固定码与任务编号。
        logger.error('execution_failed id=%s', run['id'])
        repo.fail(run['id'], worker_id)
    return True


def main():
    parser = argparse.ArgumentParser(description='Persistent operations worker')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    worker_id = f'{os.getpid()}-{uuid4()}'
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            tick(worker_id)
        except Exception:
            logger.error('worker_storage_unavailable')
            if args.once:
                return 1
        if args.once:
            return 0
        stop.wait(2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
