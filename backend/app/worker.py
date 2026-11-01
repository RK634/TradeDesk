"""Lightweight scheduled automation worker; run with `python -m app.worker`."""

import argparse
import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.automation import run_automation_cycle

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("app.worker")


def run_once() -> dict[str, int]:
    db = SessionLocal()
    try:
        return run_automation_cycle(db)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="TradeDesk scheduled notification worker")
    parser.add_argument("--once", action="store_true", help="Run one automation cycle and exit")
    args = parser.parse_args()
    if args.once:
        if not settings.automation_enabled:
            logger.info("Automation is disabled; no cycle executed.")
            return
        logger.info("Automation cycle results: %s", run_once())
        return
    logger.info("Automation worker starting (enabled=%s, interval=%ss)", settings.automation_enabled, settings.automation_poll_seconds)
    while True:
        if settings.automation_enabled:
            try:
                logger.info("Automation cycle results: %s", run_once())
            except Exception:
                logger.exception("Automation cycle failed; it will be retried on the next cycle.")
        time.sleep(settings.automation_poll_seconds)


if __name__ == "__main__":
    main()
