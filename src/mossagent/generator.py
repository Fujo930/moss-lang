"""Corvus AI generation loop — generate Moss code, verify, iterate.

The Agent's defining feature: AI writes Moss, Trust pipeline validates,
failures feed back to the LLM as structured fix hints, loop continues
until all gates pass or max retries exhausted.

No LLM dependency — callers provide a generate_fn callback.
Core is pure logic, testable without network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .core import Corvus, VerifyResult, ExecuteResult


@dataclass
class GenerationResult:
    """Full result of one generation cycle (N retries)."""
    moss_code: str
    trust: bool
    attempts: int
    verify_history: list[VerifyResult] = field(default_factory=list)
    execute_result: ExecuteResult | None = None
    final_error: str | None = None


# Prompt templates — replaceable, but these defaults encode Moss best practices
SYSTEM_PROMPT = """You are a Moss code generator. Moss is a safe, verifiable programming language.
Return ONLY valid Moss source code. No explanations, no markdown fences.

MOSS RULES:
- VALID TYPES: Number, Text, Bool, Any. DO NOT use Int, String, float, int, str.
  Parameters do NOT need type annotations. Use '->' for return type only on complex functions.
- Declare effects before use:  `effect Database` at top, then `fn save(o) uses Database { ... }`
- Every function must have a body. Use `= expr` for single-expression functions.
  Example: `fn add(x, y) = x + y` NOT `fn add(x: Number, y: Number): Number = x + y`
- Types are declared with `type Name { field: Type }`
- Match must be exhaustive (handle all variants)
- Use `require(condition, "message")` for assertions
- Use `?` operator for Result/Option propagation
- pipe operator: `x |> fn(args)` means `fn(x, args)`
- Backtick strings for interpolation: `Hello {name}!`
- Arrow body: `fn double(x) = x * 2`

BUILTIN FUNCTIONS available:
  print, len, range, assert
  textJoin, textSplit, textTrim, textChars, textSlice, textContains, textIndexOf, textReplace, textStartsWith, textEndsWith
  listNew, listPush, listGet, listSet, listSlice, listConcat, listInsert, listRemove
  mapNew, mapPut, mapGet, mapHas, mapKeys, mapValues, mapRemove
  jsonParse, jsonStringify
  readText, writeText, fileExists, listFiles, pathJoin
  httpGet, httpPostJson
  dbPut, dbGet
  processRun, processRunJson
"""

FIX_PROMPT = """Your Moss code failed Trust verification.

FAILED GATES: {failed_gates}
TRUST SCORE: {gates}/{gates_total}

FIX HINTS:
{fix_hints}

Please fix the code and return ONLY the corrected Moss source. No explanations."""


class Generator:
    """AI generation loop for Moss code.

    Usage:
        def my_llm(prompt: str) -> str:
            # call your LLM here
            return "fn add(x, y) = x + y"

        gen = Generator(Corvus(), my_llm)
        result = gen.generate("a function that adds two numbers")

        if result.trust:
            print("PASS:", result.moss_code)
        else:
            print("FAIL after", result.attempts, "attempts")
    """

    MAX_RETRIES = 5

    def __init__(self, corvus: Corvus, generate_fn: Callable[[str], str]) -> None:
        self.cv = corvus
        self.generate_fn = generate_fn

    def generate(
        self,
        spec: str,
        *,
        max_retries: int | None = None,
        system_prompt: str | None = None,
        execute_after: bool = False,
    ) -> GenerationResult:
        """Generate Moss code from a specification string.

        Args:
            spec: Human-readable specification of what the code should do.
            max_retries: Override default MAX_RETRIES.
            system_prompt: Override the default system prompt.
            execute_after: If True, run the code after trust passes.

        Returns:
            GenerationResult with full history.
        """
        retries = max_retries if max_retries is not None else self.MAX_RETRIES
        prompt = (system_prompt or SYSTEM_PROMPT) + f"\n\nTASK: {spec}\n"
        history: list[VerifyResult] = []

        for attempt in range(retries):
            try:
                code = self.generate_fn(prompt)
            except Exception as e:
                return GenerationResult(
                    moss_code="",
                    trust=False,
                    attempts=attempt + 1,
                    verify_history=history,
                    final_error=f"LLM call failed: {e}",
                )

            # Strip markdown fences if the LLM wraps output
            code = _strip_fences(code)

            vr = self.cv.verify(code)
            history.append(vr)

            if vr.trust:
                result = GenerationResult(
                    moss_code=code,
                    trust=True,
                    attempts=attempt + 1,
                    verify_history=history,
                )
                if execute_after:
                    result.execute_result = self.cv.execute(code)
                return result

            # Build fix feedback for next attempt
            hints = vr.fix_hints
            if not hints and vr.failed_gates:
                hints = [{"line": 0, "hint": f"Fix gate: {g}"} for g in vr.failed_gates]
            hint_lines = "\n".join(
                f"  - line {h.get('line', '?')}: {h.get('hint', 'unknown')}"
                for h in (hints or [{"line": 0, "hint": "Syntax or type error"}])
            )
            prompt = FIX_PROMPT.format(
                failed_gates=", ".join(vr.failed_gates or ["unknown"]),
                gates=vr.gates,
                gates_total=vr.gates_total,
                fix_hints=hint_lines,
            ) + f"\n\nCURRENT CODE:\n{code}"

        return GenerationResult(
            moss_code=code if history else "",
            trust=False,
            attempts=retries,
            verify_history=history,
            final_error=f"Failed after {retries} attempts"
            + (f": {', '.join(history[-1].failed_gates)}" if history else ""),
        )

    def safe_generate(
        self, spec: str, **kwargs
    ) -> GenerationResult:
        """Generate with execute_after=True (verify → execute)."""
        return self.generate(spec, execute_after=True, **kwargs)


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the LLM wrapped output."""
    lines = code.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines) + "\n"
