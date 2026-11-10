CREATE TABLE IF NOT EXISTS ops_automation_runs (
 id CHAR(36) PRIMARY KEY, kind VARCHAR(32) NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'queued',
 idempotency_key VARCHAR(128) NOT NULL, threshold_value INT NOT NULL,
 created_at DATETIME(6) NOT NULL, started_at DATETIME(6), finished_at DATETIME(6),
 attempts INT NOT NULL DEFAULT 0, available_at DATETIME(6) NOT NULL,
 lease_until DATETIME(6), worker_id VARCHAR(100), error VARCHAR(64), result JSON,
 UNIQUE KEY uq_automation_request (idempotency_key),
 KEY ix_automation_queue (status, available_at), KEY ix_automation_lease (status, lease_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ops_automation_todos (
 id BIGINT PRIMARY KEY AUTO_INCREMENT, store_code VARCHAR(64) NOT NULL, sku VARCHAR(128) NOT NULL,
 title VARCHAR(255) NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'open',
 available INT NOT NULL, threshold_value INT NOT NULL, updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_automation_issue (store_code, sku), KEY ix_automation_todo_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ops_automation_notifications (
 id BIGINT PRIMARY KEY AUTO_INCREMENT, run_id CHAR(36) NOT NULL,
 title VARCHAR(255) NOT NULL, body TEXT NOT NULL, is_read BOOLEAN NOT NULL DEFAULT FALSE,
 created_at DATETIME(6) NOT NULL, UNIQUE KEY uq_automation_run_notice (run_id),
 KEY ix_automation_unread (is_read, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ops_automation_schedules (
 kind VARCHAR(32) PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT FALSE,
 daily_time CHAR(5) NOT NULL DEFAULT '09:00', threshold_value INT NOT NULL DEFAULT 20,
 next_run_at DATETIME(6), KEY ix_automation_due (enabled, next_run_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ops_automation_workers (
 id VARCHAR(100) PRIMARY KEY, last_seen DATETIME(6) NOT NULL,
 KEY ix_automation_heartbeat (last_seen)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO ops_automation_schedules (kind) VALUES ('inventory_check'), ('daily_report');
