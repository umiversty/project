# Agent.md

Guidelines for an automated code‑writing assistant contributing to this repository.

## Purpose

Provide high‑quality code changes and documentation for the EBook Reader project by following the repository’s architecture, conventions, and safety constraints.

## Scope of Work

* Implement features described in issues labeled `spec:approved` or `good first issue`.
* Write tests and update docs for any change.
* Avoid large refactors unless an issue exists with consensus.

## Constraints

* Do not introduce new runtime dependencies without an ADR (Architecture Decision Record).
* Maintain accessibility and performance budgets.
* Keep public APIs backward compatible unless a major version is planned.

## Coding Conventions

* Languages: TypeScript for app and shared packages; platform languages where applicable.
* Style: follow repo ESLint/Prettier and platform linters; no `any`, prefer `unknown` with narrowing.
* Structure: new code must live in the appropriate package; wire via interfaces in `core`.
* Error handling: use typed errors or `Result` utilities; no silent catches.
* Logging: use the shared logger; no `console.log` in committed code.

## Testing Requirements

* Every PR must include tests that cover new logic.
* Target minimum 80% coverage in `core`, adapters, and AI services; avoid coverage drops.
* Provide E2E tests for user‑visible flows that cross package boundaries.

## Documentation Requirements

* Update `README` sections touched by new features.
* Add or update API docs in `packages/*/README.md`.
* Include migration notes when altering data schemas.

## Branching & Commits

* Branch from `main` using `feature/<short-description>`.
* Conventional Commits:

  * `feat(reader): add pagination cache`
  * `feat(ai-questions): support quiz generation from EPUB upload`
  * `fix(epub): handle spine items missing media-type`
  * `refactor(core): replace BookId with BrandedId`
  * `test(storage): add sqlite WAL recovery test`

## PR Checklist (Agent must verify)

* [ ] Linked issue with acceptance criteria
* [ ] Feature behind a flag if risky
* [ ] Unit and E2E tests pass locally and in CI
* [ ] A11y pass: keyboard nav, screen‑reader labels, color contrast
* [ ] Performance sanity: no regressions in pagination/render
* [ ] Docs updated (README, package docs, CHANGELOG)

## Design Contracts

* **Format Adapter Interface** `BookSource` (example):

```ts
export interface BookSource {
  canOpen(uri: string): boolean
  open(uri: string): Promise<Book>
  getToc(book: Book): Promise<Toc>
  getChapter(book: Book, id: string): Promise<Chapter>
}
```

* **AI Question Service** (example):

```ts
export interface QuestionService {
  generateQuestions(bookId: string, content: string): Promise<QuestionSet>
}
```

* **Storage Service**: must expose async CRUD with transactions and migrations.
* **Theme System**: additive tokens; no hard‑coded colors in components.

## Issue Templates (short)

* **Feature**: problem, user story, acceptance criteria, non‑goals, risks.
* **Bug**: steps to reproduce, expected, actual, logs, environment, proposed fix.

## Prompts for the Assistant

* "Implement EPUB import for multiple files dropped into the library view following the BookSource contract. Include unit tests for invalid EPUBs and update README usage."
* "Integrate AI Question Service for teacher dashboard uploads. Generate multiple‑choice questions from a chapter and create assignment records."
* "Add keyboard shortcuts for next/previous page, increase/decrease font size, and toggle theme, with an a11y review."
* "Create a storage migration to add `createdAt` to highlights; include backfill script and migration notes."

## Review Standards

* Prefer small, focused PRs.
* Block PRs lacking tests or docs.
* Request ADRs for dependency or architecture changes.

## Security & Privacy

* Never check in secrets or real user data.
* Respect OS‑level permissions; prompt before scanning directories.
* Telemetry and AI calls must be gated and anonymized, disabled by default.

## Tooling Notes

* Use current, supported API models in local tooling. Deprecated models are not allowed.
* Run `pnpm typecheck && pnpm test` before opening a PR.

## Done Definition

A change is "done" when it is merged to `main`, released behind a flag if needed, covered by tests, and documented in both README and CHANGELOG.