import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.graph import get_graph
from app.agents.state import ConversationState
from app.logging import get_logger

logger = get_logger(__name__)

# Detect if running on Hugging Face Spaces
if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"):
    SESSION_DIR = os.path.join(tempfile.gettempdir(), "chat_sessions")
    logger.info(f"Running on Hugging Face Spaces, using {SESSION_DIR}")
else:
    SESSION_DIR = Path("chat_sessions")

_CARD_FIELDS = (
    "product_handle",
    "shopify_gid",
    "shopify_product_id",
    "title",
    "vendor",
    "min_price",
    "avg_rating",
    "review_count",
    "image_url",
    "category",
)

SESSION_DIR = Path("chat_sessions")
SESSION_DIR.mkdir(exist_ok=True)


def _empty_state() -> ConversationState:
    return {
        "messages": [],
        "turn_count": 0,
        "raw_query": "",
        "normalized_query": "",
        "retrieval_query": "",
        "brand": None,
        "min_price": None,
        "max_price": None,
        "min_rating": None,
        "attributes": [],
        "semantic_constraints": [],
        "search_results": [],
        "similar_products": [],
        "detail_product": None,
        "comparison": None,
        "search_attempts": 0,
        "relaxation_budget": 3,
        "brand_was_explicit": False,
        "drop_field": None,
        "relaxation_log": [],
        "constraint_history": [],
        "needs_clarification": False,
        "clarification_question": None,
        "awaiting_user_response": False,
        "next_action": "new_search",
        "response_payload": None,
        "conversation_history": [],  # Serialized conversation with payloads
    }


def _slim_card(r: dict) -> dict:
    return {
        k: r.get(k) 
        for k in _CARD_FIELDS
    }

class ChatRunner:
    def __init__(self, session_id: Optional[str] = None, username: Optional[str] = None):
        
        logger.info(
            f"Initializing ChatRunner with Session = {session_id}"
        )

        self.graph = get_graph()
        self.session_id = session_id
        self.username = username
        self.state: ConversationState = _empty_state()
        
        if session_id and username:
            self._load_state()
    
    def _get_state_path(self) -> Path:
        return Path(SESSION_DIR) / f"{self.username}_{self.session_id}.json"
    
    def _save_state(self):
        if not self.session_id or not self.username:
            return
        
        path = self._get_state_path()
        
        # Build serializable state
        serializable = {
            "turn_count": self.state.get("turn_count", 0),
            "raw_query": self.state.get("raw_query", ""),
            "normalized_query": self.state.get("normalized_query", ""),
            "retrieval_query": self.state.get("retrieval_query", ""),
            "brand": self.state.get("brand"),
            "min_price": self.state.get("min_price"),
            "max_price": self.state.get("max_price"),
            "min_rating": self.state.get("min_rating"),
            "attributes": self.state.get("attributes", []),
            "semantic_constraints": self.state.get("semantic_constraints", []),
            "brand_was_explicit": self.state.get("brand_was_explicit", False),
            "conversation_history": self.state.get("conversation_history", []),
        }
        
        try:
            with open(path, 'w') as f:
                json.dump(serializable, f, indent=2)
                
            logger.info(
                f"State saved Session = {self.session_id}"
            )

        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def _load_state(self):
        path = self._get_state_path()
        if not path or not path.exists():
            return
        
        try:
            with open(path, 'r') as f:
                loaded = json.load(f)
            
            # Restore state
            for key, value in loaded.items():
                if key in self.state:
                    self.state[key] = value
            
            # Restore messages from conversation_history
            user_message = []
            for item in self.state.get("conversation_history", []):
                if item["role"] == "user":
                    user_message.append(HumanMessage(content=item["content"]))
                else:
                    agent_message = AIMessage(content=item["content"])
                    if item.get("payload"):
                        agent_message.additional_kwargs = {"response_payload": item["payload"]}

                    user_message.append(agent_message)
            
            self.state["messages"] = user_message
            logger.info(f"Loaded session {self.session_id} with {len(user_message)} messages")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    def _get_last_assistant_message(self) -> str:
        ai_messages = [m for m in self.state["messages"] if isinstance(m, AIMessage)]
        return ai_messages[-1].content if ai_messages else ""
    
    def _build_payload(self) -> dict:
        state = self.state
        action = state.get("next_action", "respond")
        results = state.get("search_results", [])
        comparison = state.get("comparison")
        detail_prod = state.get("detail_product")
        needs_clar = state.get("needs_clarification", False)
        
        ai_messages = [m for m in state["messages"] if isinstance(m, AIMessage)]
        text = ai_messages[-1].content if ai_messages else "I'm not sure how to help with that."
        
        meta = {
            "action": action,
            "turn": state.get("turn_count", 0),
            "result_count": len(results),
        }
        
        if needs_clar:
            return {
                "type": "clarification",
                "text": text,
                "clarification": {
                    "question": state.get("clarification_question", text),
                    "awaiting": True,
                },
                "meta": meta,
            }
        
        if action == "no_results":
            return {
                "type": "message",
                "text": text,
                "meta": meta,
            }
        
        if comparison:
            return {
                "type": "comparison",
                "text": text,
                "comparison": comparison,
                "meta": meta,
            }
        
        if action == "details":
            if not detail_prod:
                return {
                    "type": "error",
                    "text": text,
                    "meta": meta,
                }
            return {
                "type": "detail",
                "text": text,
                "detail": detail_prod,
                "meta": meta,
            }
        
        if action == "similar" and results:
            return {
                "type": "similar",
                "text": text,
                "products": [_slim_card(r) for r in results[:10]],
                "filters_applied": self.current_filters or {},
                "relaxations": state.get("relaxation_log", []),
                "meta": meta,
            }
        
        if action in ("new_search", "refine", "respond") and results:
            return {
                "type": "products",
                "text": text,
                "products": [_slim_card(r) for r in results[:10]],
                "filters_applied": self.current_filters or {},
                "relaxations": state.get("relaxation_log", []),
                "meta": meta,
            }
        
        return {
            "type": "message",
            "text": text,
            "meta": meta,
        }

    def chat(self, user_message: str) -> dict:
        # Add user message to history
        self.state["conversation_history"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        self.state = {
            **self.state,
            "messages": self.state["messages"] + [HumanMessage(content=user_message)],
            "turn_count": self.state["turn_count"] + 1,
        }
        
        self._save_state()
        
        result = self.graph.invoke(self.state.copy())
        self.state = result
        
        payload = self._build_payload()
        self.state = {**self.state, "response_payload": payload}
        
        # Store assistant message with payload
        assistant_content = self._get_last_assistant_message()
        self.state["conversation_history"].append({
            "role": "assistant",
            "content": assistant_content,
            "payload": payload,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_state()
        return payload
    
    def reset(self):
        self.state = _empty_state()
        
        if self.session_id and self.username:
            path = self._get_state_path()
        
            if path and path.exists():
                path.unlink()
    
    def get_full_conversation(self) -> list:
        """Return full conversation with payloads for frontend."""
        return self.state.get("conversation_history", [])
    
    @property
    def current_filters(self) -> dict:
        return {
            "query": self.state.get("retrieval_query"),
            "brand": self.state.get("brand"),
            "min_price": self.state.get("min_price"),
            "max_price": self.state.get("max_price"),
            "min_rating": self.state.get("min_rating"),
        }
    
    @property
    def last_results(self) -> list:
        return self.state.get("search_results", [])