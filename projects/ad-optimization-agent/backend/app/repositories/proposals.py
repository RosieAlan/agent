"""草案与审批写入独立业务库；状态变化和审计事件共用事务。"""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.business import business_engine
from app.repositories.ads import fetch_campaign_budget
from app.schemas.proposals import ProposalCreate, ProposalDecision

PUBLIC_FIELDS = ("id", "profile_id", "campaign_id", "currency", "source_budget", "proposed_budget",
                 "reason", "status", "version", "reviewer", "created_at", "updated_at")


class ProposalConflict(Exception):
    pass


class ProposalNotFound(Exception):
    pass


def _view(row):
    result = {key: row[key] for key in PUBLIC_FIELDS}
    for key in ("created_at", "updated_at"):
        result[key] = result[key].replace(tzinfo=timezone.utc)  # 库中约定保存UTC时间。
    return result


def fingerprint(body: ProposalCreate) -> str:
    payload = body.model_dump(mode="json", exclude={"idempotency_key"})
    payload["proposed_budget"] = format(body.proposed_budget.quantize(Decimal("0.01")), "f")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def get_proposal(proposal_id: str) -> dict:
    with business_engine().connect() as connection:
        row = connection.execute(text("SELECT * FROM ad_budget_proposals WHERE id=:id"),
                                 {"id": proposal_id}).mappings().first()
        if row is None:
            raise ProposalNotFound("方案不存在")
        return _view(row)


def list_proposals(limit: int) -> list[dict]:
    with business_engine().connect() as connection:
        rows = connection.execute(text("SELECT * FROM ad_budget_proposals ORDER BY created_at DESC,id DESC LIMIT :limit"),
                                  {"limit": limit}).mappings().all()
        return [_view(row) for row in rows]


def _existing(key: str, request_hash: str):
    with business_engine().connect() as connection:
        row = connection.execute(text("SELECT * FROM ad_budget_proposals WHERE idempotency_key=:key"),
                                 {"key": key}).mappings().first()
        if row is not None:
            if row["request_hash"] != request_hash:
                raise ProposalConflict("该提交编号已用于其他内容，请为新草案使用新的编号")
            return _view(row)


def _source(profile_id, campaign_id):
    snapshot = fetch_campaign_budget(profile_id, campaign_id)
    if snapshot is None:
        raise ProposalNotFound("该账户下未找到广告活动")
    if snapshot["source_budget"] is None or not snapshot["currency"]:
        raise ProposalConflict("源数据缺少预算或币种，暂时无法创建或批准方案")
    return snapshot


def _event(connection, proposal_id, event_type, version, actor, timestamp):
    connection.execute(text("""INSERT INTO ad_proposal_events
        (id,proposal_id,event_type,version,actor,created_at)
        VALUES (:id,:proposal_id,:event_type,:version,:actor,:created_at)"""), {
        "id": str(uuid4()), "proposal_id": proposal_id, "event_type": event_type,
        "version": version, "actor": actor, "created_at": timestamp,
    })


def create_proposal(body: ProposalCreate) -> dict:
    request_hash, key = fingerprint(body), str(body.idempotency_key)
    existing = _existing(key, request_hash)
    if existing is not None:
        return existing  # 同一个提交编号与内容重复到达时返回同一方案。
    snapshot = _source(body.profile_id, body.campaign_id)
    if snapshot["source_budget"] == body.proposed_budget:
        raise ProposalConflict("建议预算与当前快照相同，请确认调整内容")
    proposal_id, now = str(uuid4()), datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        with business_engine().begin() as connection:
            connection.execute(text("""INSERT INTO ad_budget_proposals
                (id,idempotency_key,request_hash,profile_id,campaign_id,currency,source_budget,
                 proposed_budget,reason,status,version,created_at,updated_at)
                VALUES (:id,:key,:hash,:profile_id,:campaign_id,:currency,:source_budget,
                 :proposed_budget,:reason,'pending_approval',1,:now,:now)"""), {
                "id": proposal_id, "key": key, "hash": request_hash,
                "profile_id": body.profile_id, "campaign_id": body.campaign_id,
                "currency": snapshot["currency"], "source_budget": snapshot["source_budget"],
                "proposed_budget": body.proposed_budget, "reason": body.reason, "now": now,
            })
            _event(connection, proposal_id, "created", 1, None, now)
    except IntegrityError:
        existing = _existing(key, request_hash)  # 并发重复提交由数据库唯一约束兜底。
        if existing is not None:
            return existing
        raise
    return get_proposal(proposal_id)


def decide_proposal(body: ProposalDecision) -> dict:
    proposal_id = str(body.proposal_id)
    proposal = get_proposal(proposal_id)
    if proposal["status"] != "pending_approval" or proposal["version"] != body.expected_version:
        raise ProposalConflict("方案状态或版本已变化，请刷新后确认")
    if body.decision == "approve":
        current = _source(proposal["profile_id"], proposal["campaign_id"])
        if current["source_budget"] != proposal["source_budget"] or current["currency"] != proposal["currency"]:
            raise ProposalConflict("源预算快照已变化，请重新建立方案")
    status = "approved" if body.decision == "approve" else "rejected"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with business_engine().begin() as connection:
        updated = connection.execute(text("""UPDATE ad_budget_proposals
            SET status=:status,version=version+1,reviewer=:reviewer,updated_at=:now
            WHERE id=:id AND version=:version AND status='pending_approval'"""), {
            "status": status, "reviewer": body.reviewer, "now": now,
            "id": proposal_id, "version": body.expected_version,
        })
        if updated.rowcount != 1:
            raise ProposalConflict("方案已被其他请求处理，请刷新后查看")
        _event(connection, proposal_id, status, body.expected_version + 1, body.reviewer, now)
    return get_proposal(proposal_id)


def list_events(proposal_id: str) -> list[dict]:
    get_proposal(proposal_id)
    with business_engine().connect() as connection:
        rows = connection.execute(text("SELECT * FROM ad_proposal_events WHERE proposal_id=:id ORDER BY version"),
                                  {"id": proposal_id}).mappings().all()
        return [{**row, "created_at": row["created_at"].replace(tzinfo=timezone.utc)} for row in rows]
