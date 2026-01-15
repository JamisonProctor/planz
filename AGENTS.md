# Repository Guidelines

## Project Structure & Module Organization
The repository is currently minimal. At the root you will find:
- `.env.example` for required environment variables.
- `.gitignore` for common Python/Node/tooling ignores.

When adding code, keep a clean, predictable layout. Recommended structure:
- `src/` for application code.
- `tests/` for automated tests.
- `scripts/` for maintenance or dev helpers.
- `docs/` for design notes or architecture docs.

## Build, Test, and Development Commands
No build or test scripts are committed yet. If you add tooling, document it in `README.md` and prefer standard entry points:
- `make dev` / `make test` if you add a `Makefile`.
- `python -m venv .venv` and `pip install -r requirements.txt` if this is a Python project.
- `npm install` and `npm test` if a `package.json` is introduced.

## Coding Style & Naming Conventions
Be explicit and consistent:
- Python: 4-space indentation, snake_case for functions and variables.
- JS/TS (if added): 2-space indentation, camelCase for functions and variables.
- Name modules by feature (`src/billing/`, `src/auth/`) rather than by type.

If you introduce formatters or linters (e.g., `ruff`, `black`, `eslint`), add configs to the repo and keep them in CI.

## Testing Guidelines
No test framework is configured yet. If you add tests:
- Python: use `pytest` and name files `tests/test_*.py`.
- JS/TS: use `vitest` or `jest` with `*.test.ts`/`*.test.js` naming.
Prefer fast, deterministic tests and cover new behavior with focused cases.

## Commit & Pull Request Guidelines
Git history uses short, imperative, sentence-case messages (e.g., "Add base .gitignore and env template"). Follow that style.

PRs should include:
- What changed and why.
- How to run or verify (commands or manual steps).
- Notes on config changes (e.g., `.env.example` updates) and any required migrations.

## Security & Configuration Tips
Never commit secrets. Add new variables to `.env.example` with safe placeholders and document required values in the PR.
