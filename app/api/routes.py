from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Tuple
import traceback
import uuid
from datetime import datetime

from app.agents.runner import ChatRunner
from app.logging import get_logger
from .models import ChatRequest, ChatResponse
from .auth import get_current_user
from app.config import settings
import asyncio

logger = get_logger(__name__)

router = APIRouter()

_sessions: Dict[Tuple[str, str], dict] = {}


def _session_key(username: str, session_id: str) -> Tuple[str, str]:
    return (username, session_id)


def _sessions_for_user(username: str) -> list:
    result = []
    for (u, sid), data in _sessions.items():
        if u == username:
            result.append({
                "session_id": sid,
                "title": data["title"],
                "created_at": data["created_at"],
                "last_active": data["last_active"],
            })
    result.sort(key=lambda x: x["last_active"], reverse=True)
    return result


@router.get("/sessions")
async def list_sessions(username: str = Depends(get_current_user)):
    return {"sessions": _sessions_for_user(username)}


@router.post("/session")
async def create_session(username: str = Depends(get_current_user)):
    try:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        key = _session_key(username, session_id)
        
        _sessions[key] = {
            "runner": ChatRunner(session_id=session_id, username=username),
            "title": "New chat",
            "created_at": now,
            "last_active": now,
        }
        return {
            "session_id": session_id,
            "title": "New chat",
            "created_at": now,
            "last_active": now,
        }
    except Exception as e:
        print(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail="Could not create session")


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, username: str = Depends(get_current_user)):
    key = _session_key(username, session_id)
    if key not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    runner = _sessions[key].get("runner")
    if runner:
        runner.reset()
    
    del _sessions[key]
    return {"deleted": session_id}


@router.patch("/session/{session_id}/title")
async def rename_session(
    session_id: str,
    body: dict,
    username: str = Depends(get_current_user),
):
    key = _session_key(username, session_id)
    if key not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    title = str(body.get("title", "")).strip()[:60] or "New chat"
    _sessions[key]["title"] = title
    return {"session_id": session_id, "title": title}


@router.get("/session/{session_id}/full")
async def get_session_full(
    session_id: str, 
    username: str = Depends(get_current_user)
):
    """Get complete session with all messages and their payloads."""
    key = _session_key(username, session_id)
    if key not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    runner = _sessions[key]["runner"]
    conversation = runner.get_full_conversation()
    
    return {
        "session_id": session_id,
        "title": _sessions[key]["title"],
        "conversation": conversation,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, username: str = Depends(get_current_user)):
    try:
        if not request.session_id:
            raise HTTPException(status_code=400, detail="session_id required")

        key = _session_key(username, request.session_id)

        if key not in _sessions:
            now = datetime.utcnow().isoformat()
            _sessions[key] = {
                "runner": ChatRunner(session_id=request.session_id, username=username),
                "title": "New chat",
                "created_at": now,
                "last_active": now,
            }

        session_data = _sessions[key]
        runner: ChatRunner = session_data["runner"]

        if session_data["title"] == "New chat" and request.message:
            session_data["title"] = request.message[:48] + ("…" if len(request.message) > 48 else "")

        session_data["last_active"] = datetime.utcnow().isoformat()

        result = await asyncio.to_thread(runner.chat, request.message)
        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        print(traceback.format_exc())
        return ChatResponse(
            type="error",
            text="Sorry, I encountered an error processing your request. Please try again.",
            meta={
                "action": "error",
                "turn": 0,
                "result_count": 0,
                "error": str(e) if getattr(settings, 'DEBUG', False) else None,
            },
        )