"""Corvus Agent — multi-turn autonomous coding agent.

The Agent loop:
  1. Receive a task description
  2. LLM explores the codebase (read_file, grep, ls, bash)
  3. LLM writes Moss code (write_file, moss_verify, moss_execute)
  4. LLM tests and fixes (bash python -m pytest, moss_verify)
  5. LLM commits (git add, git commit)
  6. Repeat until done or max rounds

Tool calling: LLM responds in JSON — either a tool call or a final answer.
"""

from __future__ import annotations

import json as _json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .core import Corvus
from .tools import dispatch_tool, TOOL_LIST


AGENT_SYSTEM_PROMPT = """You are Corvus, a Moss Agent. You write, verify, and deploy Moss code.

You have TOOLS. To use a tool, respond with JSON:
  {{"tool": "tool_name", "params": {{"arg": "value"}}}}

When you are done, respond with JSON:
  {{"done": true, "summary": "...", "moss_code": "...", "trust": true/false}}

TOOLS AVAILABLE:
{tool_descriptions}

RULES:
- YOU MUST RESPOND WITH VALID JSON ONLY. NO PROSE. NO EXPLANATIONS. NO MARKDOWN.
  Every single response must be exactly one JSON object: either a tool call or done.
- Before writing code, EXPLORE the project: use read_file, ls, grep.
- Write Moss code with write_file, then verify with moss_verify.
- If verification fails, fix the code and re-verify. DO NOT give up.
- When code passes Trust verification, test with moss_execute or bash pytest.
- Commit working code with git add + git commit.
- NEVER assume — always read files first.
- If a tool returns an error, read it, understand it, fix it.
"""


@dataclass
class AgentResult:
    ok: bool
    task: str
    rounds: int
    summary: str = ""
    moss_code: str = ""
    file_paths: list[str] = field(default_factory=list)
    trust: bool = False
    history: list[dict] = field(default_factory=list)
    elapsed_s: float = 0.0


class Agent:
    """Multi-turn autonomous Moss coding agent.

    Usage:
        from mossagent.llm import create_adapter
        from mossagent.agent import Agent

        adapter = create_adapter("openai")
        agent = Agent(adapter.generate)
        result = agent.run("Write a sorting function in Moss and verify it.")
    """

    MAX_ROUNDS = 15

    def __init__(self, generate_fn, *, max_rounds: int | None = None) -> None:
        self.generate_fn = generate_fn
        self.max_rounds = max_rounds or self.MAX_ROUNDS
        self.cv = Corvus()

    def run(self, task: str) -> AgentResult:
        """Execute a task autonomously. Returns AgentResult with full history."""
        t0 = time.perf_counter()
        history: list[dict] = []

        tool_desc = "\n".join(f"  {name}: {desc}" for name, desc in TOOL_LIST)
        system = AGENT_SYSTEM_PROMPT.format(tool_descriptions=tool_desc)

        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"TASK: {task}\n\nStart by exploring the project to understand what exists."},
        ]

        for rnd in range(self.max_rounds):
            prompt = self._build_prompt(messages)
            raw = ""
            try:
                raw = self.generate_fn(prompt)
                parsed = self._parse_response(raw)
            except Exception as e:
                history.append({"round": rnd + 1, "raw": raw, "error": str(e)})
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": f"Error parsing your response: {e}. Please respond with valid JSON."})
                continue

            history.append({"round": rnd + 1, "raw": raw, "parsed": parsed})

            if parsed.get("done"):
                return AgentResult(
                    ok=True,
                    task=task,
                    rounds=rnd + 1,
                    summary=parsed.get("summary", ""),
                    moss_code=parsed.get("moss_code", ""),
                    trust=parsed.get("trust", False),
                    history=history,
                    elapsed_s=round(time.perf_counter() - t0, 2),
                )

            if parsed.get("tool"):
                tool_name = parsed["tool"]
                params = parsed.get("params", {})
                result = dispatch_tool(tool_name, params)

                # Format result for LLM
                result_str = _json.dumps(result, indent=2)
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": f"Tool result ({tool_name}):\n{result_str}"})
                continue

            # Unrecognized response — nudge
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Please respond with a tool call ({\"tool\":...}) or done ({\"done\": true...})."})

        return AgentResult(
            ok=False,
            task=task,
            rounds=self.max_rounds,
            summary=f"Failed to complete after {self.max_rounds} rounds.",
            history=history,
            elapsed_s=round(time.perf_counter() - t0, 2),
        )

    def _build_prompt(self, messages: list[dict]) -> str:
        """Build a single prompt string from message history.
        
        For providers that support chat format natively, this is split into
        system + user messages.  For simpler providers, we flatten to text.
        """
        # Flatten to text — works with all LLMs
        parts = []
        for m in messages[-6:]:  # last 6 messages to avoid overflow
            role = m["role"]
            content = m["content"]
            if role == "system":
                parts.append(content)
            elif role == "user":
                parts.append(f"\nUSER: {content}")
            elif role == "assistant":
                parts.append(f"\nASSISTANT: {content}")
        return "\n".join(parts)

    def _parse_response(self, raw: str) -> dict:
        """Parse LLM response into a tool call or done signal."""
        # Strip markdown fences
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Try JSON first
        try:
            return _json.loads(text)
        except _json.JSONDecodeError:
            pass

        # Extract first balanced JSON object (handles nested braces)
        start = text.find("{")
        if start >= 0:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return _json.loads(text[start:i + 1])
                        except _json.JSONDecodeError:
                            break

        # Fallback: if the LLM just wrote code, treat it as done
        if "fn " in text or "effect " in text or "type " in text or "rule " in text:
            return {"done": True, "summary": "LLM returned raw code.", "moss_code": text, "trust": False}

        raise ValueError(f"Could not parse LLM response as tool call or done signal. Got: {text[:300]}")
