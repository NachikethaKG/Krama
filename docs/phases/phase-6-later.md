# Phase 6: Later (backlog)

Not planned in detail. Each item becomes its own phase file once we decide to do it. Proposed owners follow the module split ([ADR 0001](../adr/0001-ownership-by-module.md)) and can change.

| Idea | Proposed owner | Research to do first |
|---|---|---|
| **"Do it for me"**: run a stored verified workflow for the user | Vishwas | Which workflows are safe to replay without re-planning? How do policy confirmations work for one-click execution? |
| **Browser extension**: record a human doing a task, then turn it into a workflow | Nachiketha | Chrome Manifest V3 limits; recording with rrweb from a content script; mapping human clicks to steps with expected states |
| **Human takeover** during a run (after CAPTCHA / login) | Vishwas + Nachiketha | Streaming a remote browser (CDP screencast, noVNC) vs handing control to the user's own browser |
| **Multiple languages** (UI, captions, narration) | Nachiketha | i18n in Next.js; translating instruction text without changing quoted UI labels; Piper voices per language |
| **Enterprise**: RBAC, teams, audit log | Vishwas | Role models (owner/editor/viewer), row-level permissions in Postgres, audit-log design |
| **Public API** for workflows and tutorials | Vishwas | API keys, rate limiting, versioned public endpoints |
| **Workflow knowledge base**: search across all verified workflows | Nachiketha | Full-text search in Postgres vs a vector index; ranking by freshness and validation status |
| **Desktop and mobile apps** | — | Accessibility APIs (UI Automation on Windows), Appium; very different from browsers, so a separate project decision |
