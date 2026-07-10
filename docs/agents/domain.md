# Domain Docs

This is a single-context repository. Engineering skills should use the project's domain documentation when exploring or changing the codebase.

## Before exploring

- Read `CONTEXT.md` at the repository root.
- Read ADRs under `docs/adr/` that affect the area being changed.
- If a document does not exist, proceed silently rather than creating it preemptively.

## Use the glossary vocabulary

Use domain terms as defined in `CONTEXT.md` in issue titles, implementation plans, tests, and code. If a needed concept is absent, reconsider whether new terminology is necessary or note the gap for domain modeling.

## Flag ADR conflicts

Surface any proposal that contradicts an accepted ADR rather than silently overriding it.
