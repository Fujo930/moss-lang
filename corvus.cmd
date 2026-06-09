@echo off
:: Corvus — Moss Agent CLI launcher
:: Usage: corvus verify file.moss    corvus generate --spec "desc"    corvus version
::
:: Set LLM_API_KEY to your API key before using generate:
::   set LLM_API_KEY=sk-...
::   corvus generate --spec "sort a list" --provider openai
::
:: For local models (Ollama / LM Studio):
::   set LLM_BASE_URL=http://localhost:1234/v1
::   corvus generate --spec "..." --provider local

python -m mossagent.cli %*
