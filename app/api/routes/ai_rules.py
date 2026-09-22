from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.api.models.ai_rule import AiRuleCreateRequest, AiRuleItem
from app.api.controllers.auth import require_user

router = APIRouter()

MAX_RULES = 50
MAX_TEXT_CHARS = 500


@router.get("", response_model=list[AiRuleItem])
def list_rules(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        rows = db.execute(
            text("SELECT id, text FROM ai_rules WHERE user_id = :user_id ORDER BY id"),
            {"user_id": row[0]}
        ).fetchall()
        return [AiRuleItem(id=r[0], text=r[1]) for r in rows]
    finally:
        db.close()


@router.post("", response_model=AiRuleItem)
def create_rule(req: AiRuleCreateRequest, authorization: str = Header(None)):
    content = req.text.strip()
    if not content or len(content) > MAX_TEXT_CHARS:
        raise HTTPException(status_code=422, detail=f"Rule must be 1-{MAX_TEXT_CHARS} characters")
    db, row = require_user(authorization)
    try:
        count = db.execute(
            text("SELECT COUNT(*) FROM ai_rules WHERE user_id = :user_id"),
            {"user_id": row[0]}
        ).scalar()
        if count is not None and count >= MAX_RULES:
            raise HTTPException(status_code=422, detail=f"Rules limited to {MAX_RULES}")
        result = db.execute(
            text("INSERT INTO ai_rules (user_id, text) VALUES (:user_id, :text)"),
            {"user_id": row[0], "text": content}
        )
        db.commit()
        return AiRuleItem(id=result.lastrowid, text=content)
    finally:
        db.close()


@router.delete("")
def delete_all_rules(authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        db.execute(
            text("DELETE FROM ai_rules WHERE user_id = :user_id"),
            {"user_id": row[0]}
        )
        db.commit()
        return {"detail": "All rules deleted"}
    finally:
        db.close()


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, authorization: str = Header(None)):
    db, row = require_user(authorization)
    try:
        existing = db.execute(
            text("SELECT id FROM ai_rules WHERE id = :id AND user_id = :user_id"),
            {"id": rule_id, "user_id": row[0]}
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Rule not found")
        db.execute(
            text("DELETE FROM ai_rules WHERE id = :id"),
            {"id": rule_id}
        )
        db.commit()
        return {"detail": "Rule deleted"}
    finally:
        db.close()
