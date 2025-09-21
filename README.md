# README

## Project: EBook Reader

A cross‑platform eBook reader optimized for a smooth, customizable reading experience and efficient digital library management. The app focuses on usability, accessibility, and features that make reading more enjoyable and convenient. It also allows educators to upload PDFs/EPUBs, automatically generate comprehension questions through an AI model, and create assignments directly from the teacher dashboard.

---

## Objectives

* Provide a clean, distraction‑free reading interface with robust typography and layout controls.
* Support common formats (e.g., EPUB, PDF, MOBI where licensing permits) via pluggable parsers.
* Deliver reliable library management: import, metadata, search, tags, progress sync.
* Enable teachers to upload PDF/EPUB files, trigger AI‑generated question sets, and assign them to students via a dashboard.
* Ensure accessibility (screen readers, keyboard navigation, adjustable contrast and font sizes).
* Be modular so new formats, themes, and services can be added without refactoring the core.

---

## Key Features (MVP)

* Import and parse EPUB; basic PDF viewing.
* Library with search, filters, tags, and reading progress.
* Reader: pagination, font size/line height/margins, themes (light/dark/sepia), TOC navigation, bookmarks, highlights, notes.
* Teacher Dashboard: upload books, generate AI‑based questions, build assignments, and distribute them.
* Settings synced locally (with optional cloud sync module).
* Keyboard shortcuts and screen‑reader support for core actions.

---

## Architecture Overview

* **App Shell (UI)**: React/React Native, SwiftUI/Kotlin, or Electron; view components are state‑driven.
* **Core Domain**: Pure logic for books, library, reading sessions, highlights, annotations, and assignment handling.
* **Format Adapters**: EPUB/PDF/MOBI loaders implementing a common `BookSource` interface.
* **AI Question Service**: API client connecting to the model for generating quizzes and questions from uploaded content.
* **Teacher Dashboard**: Interfaces for uploading files, previewing questions, creating assignments, and monitoring completion.
* **Storage Layer**: Local DB (SQLite/Room/Core Data) and file storage. Optional cloud sync behind an interface.
* **Services**: Search/indexing, metadata fetch, theming, telemetry (privacy‑respecting).
* **Bridge**: IPC or module boundary between UI and core for portability and testing.

```
UI <-> App Services <-> Core Domain <-> Storage
                     \-> Format Adapters
                     \-> AI Question Service
```

---

## Tech Stack (suggested)

* **Language**: TypeScript (for web/desktop) or Kotlin/Swift for mobile. Shared core can be TS or Rust.
* **UI**: React + Vite/Electron or React Native.
* **State**: Redux Toolkit/Zustand or platform equivalents.
* **DB**: SQLite (via better‑sqlite3, Room, Core Data) with a lightweight ORM.
* **Testing**: Vitest/Jest, Playwright for E2E; ktlint/SwiftLint where relevant.
* **CI**: Lint, typecheck, unit tests, E2E on PR.

---

## Folder Structure (reference)

```
/reader
  /apps
    /desktop        # Electron app shell
    /mobile         # React Native app shell
    /web            # PWA shell (optional)
    /teacher        # Teacher dashboard interface
  /packages
    /core           # Domain models, use cases, services
    /formats        # EPUB/PDF/MOBI adapters
    /ui             # Shared UI components/styles
    /storage        # DB, filesystem, sync interfaces
    /ai-questions   # Question generation service
    /testing        # Test utilities and fixtures
```

---

## Setup

1. Clone repo and install deps

```
# node example
pnpm i
pnpm -w build
```

2. Run the desktop/web app

```
pnpm dev:desktop
pnpm dev:web
```

3. Run the teacher dashboard

```
pnpm dev:teacher
```

4. Run tests and linters

```
pnpm test
pnpm typecheck
pnpm lint
```

---

## Environment

Create `.env.local` with any secrets or feature flags. Example:

```
APP_ENV=dev
FEATURE_SYNC=false
TELEMETRY_OPT_IN=false
AI_API_KEY=sk-xxxx
```

---

## Coding Standards

* Type‑safe APIs; no implicit `any`.
* Pure functions in `core`; isolate side effects in services.
* Keep adapters small and well‑tested; prefer interfaces and dependency injection.
* Accessibility: all interactive elements keyboard‑reachable; high‑contrast themes supported.
* Performance: lazy load heavy assets; avoid layout thrash in pagination.

---

## Testing Strategy

* Unit tests for domain logic and adapters.
* Contract tests for `BookSource`, storage, and AI Question Service interfaces.
* Snapshot tests for reader components only where structure is stable.
* E2E happy path: import book, open, paginate, add bookmark/highlight, generate questions, assign to class, relaunch and restore state.

---

## Roadmap (high level)

1. MVP: EPUB import, basic reader, library, persistence.
2. Teacher dashboard with PDF/EPUB upload and AI‑generated question sets.
3. Accessibility polish and keyboard shortcuts.
4. PDF improvements, annotations, export/import highlights.
5. Sync module and multi‑device progress.
6. Marketplace for themes/plugins.

---

## License & Privacy

* Store user data locally by default. Make telemetry opt‑in and anonymous.
* AI question generation uses external APIs; do not send sensitive student data.
* Include a permissive license compatible with third‑party format libraries.


