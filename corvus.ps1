# Corvus — Moss Agent CLI launcher (PowerShell)
# Usage: .\corvus.ps1 verify file.moss    .\corvus.ps1 generate --spec "desc"
#
# Set environment variables before use:
#   $env:LLM_API_KEY = "sk-..."
#   $env:LLM_MODEL = "gpt-4o"
#   $env:LLM_BASE_URL = "http://localhost:1234/v1"  # for local

python -m mossagent.cli $args
