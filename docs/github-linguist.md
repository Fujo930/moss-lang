# GitHub Linguist support

GitHub cannot display `Moss` in the repository language bar until Moss is added
to the upstream `github-linguist/linguist` language list.

The public positioning is: Moss is an AI-designed and AI-built programming
language prototype by Codex and Fujo930. The repository contains real `.moss`
programs and self-hosting preview files, but GitHub's global language database
does not know the language yet.

Local repository setup already done:

- `.moss` files are marked detectable in `.gitattributes`
- README shows a visible `Language: Moss` badge
- README shows `Built by Codex` and `version 0.2.0` badges
- `examples/self_host` contains real Moss source samples for future Linguist
  fixtures

Upstream checklist:

- add `Moss` to Linguist `languages.yml`
- register `.moss` as the extension
- add sample files from `examples/*.moss` and `examples/self_host/*.moss`
- provide a public repo link showing active use

Until then, GitHub may classify most of the repository as Python because the
host interpreter is written in Python. That is expected.
