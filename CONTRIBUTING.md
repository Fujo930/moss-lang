# Contributing to Moss

Moss is an experimental, AI-designed and AI-built programming language for
long-lived projects maintained by humans and AI agents.

The project welcomes small, concrete contributions while its language and
self-hosting architecture are still evolving.

## Good first contributions

- run Moss on another operating system and report the result
- improve an error message or diagnostic location
- add a focused example program
- improve editor syntax highlighting
- document a confusing command or language behavior
- add a test for an uncovered edge case

Before implementing a large language feature, open an issue so its effect on
the roadmap, self-hosting path, and compatibility model can be discussed.

## Development setup

```powershell
python -m pip install -e .
python -m unittest discover -s tests -q
python -m mosslang.cli project-check --locked .
python -m mosslang.cli selfhost --quick
```

For the complete self-hosting verification:

```powershell
python -m mosslang.cli project-test --locked .
python -m mosslang.cli selfhost-compare examples
```

## Contribution expectations

- keep changes focused and explain the behavior they alter
- add or update tests for observable behavior
- preserve deterministic output and explicit effect boundaries
- do not describe Moss as production-ready or fully self-hosted
- update relevant documentation when commands or language behavior change

By contributing, you agree that your contribution is licensed under the MIT
License.
