# GitHub Linguist support

GitHub cannot display `Moss` in the repository language bar until Moss is added
to the upstream `github-linguist/linguist` language list.

Local repository setup already done:

- `.moss` files are marked detectable in `.gitattributes`
- README shows a visible `Language: Moss` badge
- `examples/self_host` contains real Moss source samples for future Linguist
  fixtures

Upstream checklist:

- add `Moss` to Linguist `languages.yml`
- register `.moss` as the extension
- add sample files from `examples/*.moss` and `examples/self_host/*.moss`
- provide a public repo link showing active use
