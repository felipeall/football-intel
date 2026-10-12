# Conventions

## Commits

Commit messages follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

- **description**: imperative, lowercase, no trailing period, ≤ 72 characters (`add sofascore lineups activity`).
- **body**: explains *why*, when the subject does not make it obvious. Wrap at 72 characters.
- **footers**: `Refs: ADR-0006`, `Closes #12`, `BREAKING CHANGE: <what changed and how to migrate>`.

### Types

| Type | Use for |
|---|---|
| `feat` | a new capability |
| `fix` | a bug fix |
| `docs` | documentation only (README, ADRs, `GLOSSARY.md`) |
| `refactor` | code change that neither fixes a bug nor adds a feature |
| `perf` | performance improvement |
| `test` | adding or correcting tests or evals |
| `build` | dependencies, packaging, Docker images |
| `ci` | GitHub Actions and other CI configuration |
| `chore` | maintenance that touches no source or test code |
| `revert` | reverting a previous commit |

### Scopes

Use the area of the codebase the change touches:

`sources`, `transfermarkt`, `sofascore`, `understat`, `workflows`, `identity`, `dbt`, `profiles`, `agent`, `mcp`, `evals`, `web`, `infra`, `skills`.

Omit the scope when a change spans several areas.

### Breaking changes

Mark with `!` after the type/scope **and** a `BREAKING CHANGE:` footer:

```
feat(mcp)!: rename similar_players tool to find_similar_players

BREAKING CHANGE: MCP clients must call find_similar_players.
```

### Examples

```
feat(sofascore): ingest per-player heatmaps
fix(identity): normalise diacritics before name matching
docs(adr): add ADR-0022 for WhoScored source
ci: run eval suite on pull requests
```

## Branches and pull requests

- `main` is always releasable.
- One branch per change: `<type>/<short-description>` (`feat/sofascore-heatmaps`), merged by pull request with green CI.
- CI (`.github/workflows/ci.yml`) runs `ruff`, `pyright`, `pytest`, `import-linter` and `gitleaks` on every pull request and push to `main`; `main` requires all of them to pass.
- Pull request titles follow the commit format; squash-merge so the title becomes the commit on `main`.

## Decisions

- Every architectural decision gets an ADR in `docs/adr/NNNN-short-title.md`, and a line in `docs/adr/README.md`.
- Superseding a decision: write a new ADR and set the old one's status to `Superseded by ADR-NNNN`.
- New domain terms go in `GLOSSARY.md` in the same change that introduces them.
