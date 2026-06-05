# Moss ecosystem and adoption plan

Moss currently has a working language, project model, editor-facing compiler
surfaces, and a verified self-host frontend. Its next constraint is adoption:
people need a clear reason to try it and a short path from discovery to useful
work.

## Product position

Moss is for long-lived projects maintained by humans and AI agents. Its
distinctive promise is that business rules are explainable, effects are
visible, and compiler/project outputs are deterministic and structured.

"AI-built programming language" explains the project's origin. It is not the
long-term reason to use Moss.

## Adoption sequence

1. Make the first run take less than five minutes through a VS Code extension,
   hosted playground, templates, and cross-platform installers.
2. Demonstrate Moss with a realistic approval, order, refund, or permission
   rules project whose decisions produce source-mapped traces.
3. Publish short development notes showing concrete behavior, especially
   human/AI collaboration, explicit effects, and self-host progress.
4. Invite small contributions in examples, editor integrations, standard
   library functions, diagnostics, and cross-platform testing.
5. Distribute releases and showcases through GitHub Discussions, Reddit,
   Hacker News, YouTube, and programming-language communities.

## External ecosystem compatibility

Moss will reuse mature ecosystems in layers:

- 0.6: controlled subprocess integration through an explicit `Process` effect
  and deterministic JSON messages
- 0.7: typed Python FFI prototype and generated declarations under an explicit
  `Python` effect
- 0.8: stable Python binding workflow, then typed Node/JavaScript bindings
  under an explicit `JavaScript` effect

Bindings should not expose arbitrary host objects by default. Generated Moss
declarations, explicit capabilities, deterministic data boundaries, and clear
exception mapping preserve the properties that distinguish Moss.

## Ecosystem priorities

Before a public package registry, Moss needs:

- excellent editor and installation experience
- tutorials and several high-quality example projects
- CI templates and reliable cross-platform releases
- a stable, documented standard library
- explicit module visibility and compatibility rules
- a backlog of approachable contribution tasks

A registry arrives only after Moss can make meaningful compatibility promises.

## Success measures

- time from discovery to first successful Moss run
- successful editor and compiler installations
- projects created outside the main repository
- issues, discussions, and merged external contributions
- users returning after their first experiment
- active compiler stages implemented in Moss
