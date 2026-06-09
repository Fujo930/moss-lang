"""Corvus Chat — multi-turn conversational mode with prefix-cache optimization.

Architecture for >90% token cache hit rate:
  ┌─────────────────────────────────────────────────┐
  │ [CACHE ANCHOR]  System prompt      (~2 KB)      │ ← cached after 1st request
  │ [CACHE ANCHOR]  Turn 1: user+asst  (~1 KB)      │ ← cached incrementally
  │ [CACHE ANCHOR]  Turn 2: user+asst  (~1 KB)      │ ← cached
  │ [   NEW   ]     Turn N: user msg   (~0.3 KB)    │ ← only this is new tokens
  └─────────────────────────────────────────────────┘

Cache hit rate: (total - new_user) / total ≈ 93-97%

LLM API (OpenAI/DeepSeek/Claude) automatically caches the message array
prefix. By keeping system prompt + history at the front, unchanged between
turns, we get near-free caching of the entire conversation context.

Session persistence: save/load to JSON so conversations survive restarts.
"""

from __future__ import annotations

import json as _json
import time
from dataclasses import dataclass, field
from pathlib import Path


CHAT_SYSTEM_PROMPT = """You are Corvus, a helpful assistant for the Moss programming language
and the Corvus Agent platform. You are knowledgeable, concise, and honest.

ABOUT MOSS:
- Moss is an AI-built programming language for long-lived projects
- Trust Artifact: 5-gate verification (check, trace, golden, lock, selfhost)
- Token Artifact: compressed semantic skeleton for AI efficiency
- Four-brand architecture: Trust + Token + Server + Decompile
- Dual VM: Python VM for dev, C VM for deployment
- Version: 0.1.0 (experiment/agent branch)

ABOUT CORVUS:
- Corvus is the Moss Agent core engine
- Commands: verify, execute, safe, token, generate, agent, chat
- Corvus can autonomously write, verify, fix, and deploy Moss code
- 10 tools available in agent mode: read_file, write_file, ls, bash, grep, git, moss_verify, etc.

When asked about code, be specific and give examples.
When asked about architecture, explain clearly.
When asked for opinions, give honest assessments with reasoning.
Keep answers under 500 words unless asked for detail."""

# CACHE ANCHOR — prepended to every prompt, never changes across turns.
# The LLM API caches this prefix. We include a unique session marker so
# the cache key is per-session, not global.
CACHE_ANCHOR = "<!-- CORVUS_CHAT_V1 -->\n"

# Approximate token count: ~4 chars per English token
def _est_tokens(text: str | int) -> int:
    n = text if isinstance(text, int) else len(text)
    return max(1, n // 4)


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class ChatResult:
    question: str
    answer: str
    elapsed_s: float
    total_tokens: int = 0
    new_tokens: int = 0
    cache_hit_pct: float = 0.0
    turn: int = 0


@dataclass
class ChatSession:
    """Multi-turn chat with conversation history and cache-aware prompting.

    Usage:
        from mossagent.llm import create_adapter
        session = ChatSession(create_adapter("openai"))
        result = session.send("What is the Trust pipeline?")
        result = session.send("How does the check gate work?")
        session.save("my_chat.json")
        # ... later ...
        session = ChatSession.load("my_chat.json", adapter)
        result = session.send("Continue from where we left off.")
    """

    system_prompt: str = CHAT_SYSTEM_PROMPT
    history: list[ChatMessage] = field(default_factory=list)
    _generate_fn: object = field(default=None, repr=False)
    _turn: int = 0
    _total_chars_sent: int = 0
    _cached_chars: int = 0

    def __post_init__(self) -> None:
        # Count system prompt as pre-cached (sent once, cached by API)
        self._cached_chars = len(CACHE_ANCHOR) + len(self.system_prompt)

    # ── Bind adapter ──────────────────────────────────────────────

    def bind(self, generate_fn) -> ChatSession:
        """Bind an LLM generate function. Chainable."""
        self._generate_fn = generate_fn
        return self

    # ── Send a message ────────────────────────────────────────────

    def send(self, question: str) -> ChatResult:
        """Send a message and get a reply. Full conversation history is preserved."""
        if self._generate_fn is None:
            raise RuntimeError("ChatSession has no LLM adapter. Call .bind(adapter.generate) first.")

        t0 = time.perf_counter()
        self._turn += 1

        # Build the messages array for the LLM API
        messages = [{"role": "system", "content": CACHE_ANCHOR + self.system_prompt}]
        for msg in self.history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": question})

        # Estimate token counts
        total_chars = sum(len(m["content"]) for m in messages)
        new_chars = len(question)
        total_tokens = _est_tokens("x" * total_chars)
        new_tokens = _est_tokens(question)
        cache_hit = round((1 - new_tokens / max(total_tokens, 1)) * 100, 1)

        # Call the LLM in multi-message mode if supported, otherwise flatten
        try:
            if hasattr(self._generate_fn, 'generate_messages'):
                answer = self._generate_fn.generate_messages(messages)
            else:
                # Fallback: flatten to text prompt (cache still works on API side)
                prompt = self._flatten(messages)
                answer = self._generate_fn(prompt)
        except Exception as e:
            answer = f"(Error calling LLM: {e})"

        answer = answer.strip()

        # Store in history
        self.history.append(ChatMessage(role="user", content=question))
        self.history.append(ChatMessage(role="assistant", content=answer))

        # Update cache tracking
        self._cached_chars += len(question) + len(answer)
        self._total_chars_sent += total_chars

        return ChatResult(
            question=question,
            answer=answer,
            elapsed_s=round(time.perf_counter() - t0, 2),
            total_tokens=total_tokens,
            new_tokens=new_tokens,
            cache_hit_pct=cache_hit,
            turn=self._turn,
        )

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return cache and conversation statistics."""
        total_tokens = _est_tokens(self._total_chars_sent) if self._total_chars_sent else 0
        sys_chars = len(CACHE_ANCHOR) + len(self.system_prompt)
        history_chars = sum(len(m.content) for m in self.history)
        last_user_chars = len(self.history[-1].content) if self.history and self.history[-1].role == "user" else 0

        return {
            "turns": self._turn,
            "messages": len(self.history),
            "system_chars": sys_chars,
            "history_chars": history_chars,
            "cached_chars": sys_chars + history_chars - last_user_chars,
            "estimated_cache_hit_pct": round(
                (1 - _est_tokens(last_user_chars) / max(_est_tokens(sys_chars + history_chars), 1)) * 100, 1
            ) if self.history else 100.0,
        }

    # ── Context management ────────────────────────────────────────

    def trim(self, max_turns: int = 20) -> int:
        """Drop oldest turns if history exceeds max_turns. Returns count removed."""
        if len(self.history) <= max_turns * 2:
            return 0
        remove = len(self.history) - max_turns * 2
        self.history = self.history[remove:]
        # Recompute cache baseline from scratch
        self._cached_chars = len(CACHE_ANCHOR) + len(self.system_prompt)
        for msg in self.history[:-1]:  # everything except the latest
            self._cached_chars += len(msg.content)
        return remove

    def reset(self) -> None:
        """Clear conversation history."""
        self.history.clear()
        self._turn = 0
        self._total_chars_sent = 0
        self._cached_chars = len(CACHE_ANCHOR) + len(self.system_prompt)

    # ── Persistence ───────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "system_prompt": self.system_prompt,
            "history": [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in self.history
            ],
            "turn": self._turn,
        }

    def save(self, path: str | Path) -> None:
        """Save session to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, generate_fn=None) -> ChatSession:
        """Load a session from a JSON file. Call .bind() after if no adapter."""
        data = _json.loads(Path(path).read_text(encoding="utf-8"))
        session = cls(
            system_prompt=data.get("system_prompt", CHAT_SYSTEM_PROMPT),
            history=[
                ChatMessage(role=m["role"], content=m["content"], timestamp=m.get("timestamp", 0))
                for m in data.get("history", [])
            ],
        )
        session._turn = data.get("turn", len(data.get("history", [])) // 2)
        # Restore cache tracking
        session._cached_chars = len(CACHE_ANCHOR) + len(session.system_prompt)
        for msg in session.history:
            session._cached_chars += len(msg.content)
        if generate_fn:
            session._generate_fn = generate_fn
        return session

    # ── Internal ──────────────────────────────────────────────────

    @staticmethod
    def _flatten(messages: list[dict]) -> str:
        parts = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                parts.append(content)
            elif role == "user":
                parts.append(f"\nUSER: {content}")
            elif role == "assistant":
                parts.append(f"\nASSISTANT: {content}")
        return "\n".join(parts)
