"""Single worker deployment: require its database heartbeat within 30 seconds."""
from sqlalchemy import text
from db import engine

with engine.connect() as conn:
    alive = conn.execute(text("SELECT COUNT(*) FROM ops_automation_workers WHERE last_seen > UTC_TIMESTAMP(6) - INTERVAL 30 SECOND")).scalar_one()
    if alive < 1:
        raise SystemExit(1)
