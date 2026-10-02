## What & why

Closes #

## Area
- [ ] backend (Vishwas)  - [ ] frontend / packages (Nachiketha)  - [ ] contracts  - [ ] shared

## Contract impact
- [ ] none  - [ ] additive (minor bump)  - [ ] breaking (major bump + ADR)

## Screenshots / GIF (UI changes)

## Definition of Done ([details](../docs/development-workflow.md#5-definition-of-done))
- [ ] Implements the issue's "Done when"
- [ ] Tests: happy path + at least one failure/edge case
- [ ] Lint + type check pass
- [ ] Works with mocks, and with the real dependency if it exists yet
- [ ] Tested on Nachiketha's laptop (required if this touches runtime behaviour, infra or deps)
- [ ] Contract fixtures still validate; docs updated if behaviour/API changed
- [ ] No secrets, unmasked credentials or real personal data
- [ ] Only files in my area changed (or labelled `cross-boundary` and the other owner reviewed)

---
### Reviewer checklist
Works? · Architecture/seams respected? · Tests incl. failure case? · Clear naming? · Breaks the other module? · Unneeded or GPU-only deps? · Error handling? · Safety (masking, untrusted page text, destructive actions)? · Docs?
Comment prefixes: `blocker:` / `question:` / `nit:`
