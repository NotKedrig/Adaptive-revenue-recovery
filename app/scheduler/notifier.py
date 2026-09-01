"""
app/scheduler/notifier.py — Local background scheduler (Phase 1).

Preserves the reusable apscheduler infrastructure.
Recovery campaign scheduling (retries, SMS, emails) will be implemented in later phases.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# Global scheduler singleton
scheduler = BackgroundScheduler()
_is_started = False

def start_scheduler():
    global _is_started
    if _is_started:
        return
        
    scheduler.start()
    _is_started = True
    logger.info("Local APScheduler started for AI Revenue Recovery.")
