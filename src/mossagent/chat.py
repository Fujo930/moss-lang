"""Corvus Chat — single-turn conversational mode.

Unlike Agent (multi-turn tool-use), Chat is a simple Q&A loop.
No tools, no code generation requirement. The LLM answers questions
about Moss, Corvus, or any topic in natural language.

Usage:
    from mossagent.chat import Chat
    c = Chat(adapter.generate)
    answer = c.ask("What is the Trust pipeline?")
"""

from __future__ import annotations

import time
from dataclasses import dataclass


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


@dataclass
class ChatResult:
    question: str
    answer: str
    elapsed_s: float


class Chat:
    """Single-turn conversational interface."""

    def __init__(self, generate_fn, *, system_prompt: str | None = None) -> None:
        self.generate_fn = generate_fn
        self.system_prompt = system_prompt or CHAT_SYSTEM_PROMPT

    def ask(self, question: str) -> ChatResult:
        """Ask a question, get an answer. Single turn, no tools."""
        t0 = time.perf_counter()

        prompt = f"{self.system_prompt}\n\nUSER QUESTION: {question}\n\nAnswer concisely:"
        try:
            answer = self.generate_fn(prompt)
        except Exception as e:
            answer = f"(Error calling LLM: {e})"

        return ChatResult(
            question=question,
            answer=answer.strip(),
            elapsed_s=round(time.perf_counter() - t0, 2),
        )
