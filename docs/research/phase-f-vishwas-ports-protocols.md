# Ports: typing.Protocol vs abc.ABC

- **Phase:** F (Sprint F2)
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** `typing.Protocol` vs `abc.ABC` for the `backend/app/ports/` interfaces. How does strict mypy check that a class satisfies a Protocol?

## Findings
- Tested with mypy **2.4.0** `--strict`, Python 3.12 [verified locally]
- **Protocol (structural typing):** an implementation doesn't inherit or import anything from the interface. mypy checks the match wherever the class is *used as* the protocol type:
  - `x: Policy = BrokenPolicy()` → `Incompatible types in assignment`, with an "Expected / Got" listing of the mismatched method [verified locally]
  - passing it to a function that takes `Policy` → `incompatible type … expected "Policy"` [verified locally]
- **`@runtime_checkable` only checks that method names exist.** `isinstance(BrokenPolicy(), Policy)` returned `True` even with a wrong signature and return type [verified locally]. Runtime checks are therefore no substitute for mypy.
- **ABC (nominal typing):** implementations must inherit the base class. mypy reports `Cannot instantiate abstract class … with abstract attribute` when a method is missing [verified locally]. It couples modules through inheritance, so Nachiketha's `policy/` would import from the base class.

## Recommendation
**Decision (Vishwas): use `typing.Protocol`** for every port.
- Ports live in `backend/app/ports/` and use only contract types (generated models) in their signatures.
- `ports/fakes.py` provides one fake per port.
- **Each real implementation gets a typed conformance line in its own module's tests**, e.g. in `backend/tests/policy/test_conformance.py`: `_: Policy = RulePolicy()`. Strict mypy then fails the moment an implementation drifts from its port. Without such a line, mypy only checks the match where the object is passed in.
- Don't rely on `@runtime_checkable` + `isinstance` for safety. Use it only for debugging, if at all.

## Open questions
- Should ports be `async`? The agent uses Playwright's async API, so `Observer.capture` probably needs to be `async def`. Decide when writing ports v1 (#13) together with Nachiketha.

## Links
- https://typing.python.org/en/latest/spec/protocol.html
- https://mypy.readthedocs.io/en/stable/protocols.html
