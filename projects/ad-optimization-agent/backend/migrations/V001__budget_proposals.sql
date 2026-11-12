CREATE TABLE IF NOT EXISTS ad_budget_proposals (
    id CHAR(36) PRIMARY KEY,
    idempotency_key CHAR(36) NOT NULL UNIQUE,
    request_hash CHAR(64) NOT NULL,
    profile_id VARCHAR(20) NOT NULL,
    campaign_id VARCHAR(20) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    source_budget DECIMAL(14,2) NOT NULL,
    proposed_budget DECIMAL(14,2) NOT NULL,
    reason VARCHAR(1000) NOT NULL,
    status VARCHAR(24) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    reviewer VARCHAR(100) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    INDEX ix_proposal_created (created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ad_proposal_events (
    id CHAR(36) PRIMARY KEY,
    proposal_id CHAR(36) NOT NULL,
    event_type VARCHAR(24) NOT NULL,
    version INT NOT NULL,
    actor VARCHAR(100) NULL,
    created_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_proposal_event_version (proposal_id, version),
    CONSTRAINT fk_proposal_event FOREIGN KEY (proposal_id) REFERENCES ad_budget_proposals(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
