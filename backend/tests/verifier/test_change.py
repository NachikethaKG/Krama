"""The expected state of a step, from what its action changed (#469)."""

from datetime import UTC, datetime

from app.contracts_gen.common_schema import Action, ExpectedState, Target
from app.ports.models import ObservedState
from app.verifier import RuleVerifier
from app.verifier.change import observed_change

TODO_EMPTY = '- main:\n  - heading "todos" [level=1]\n  - textbox "What needs to be done?"'
TODO_TYPED = TODO_EMPTY + ": Buy milk"
TODO_ADDED = (
    TODO_EMPTY
    + """
  - list:
    - listitem:
      - checkbox "Toggle Todo"
      - text: Buy milk
      - button "Delete"
  - status: 1 item left"""
)
TODO_DONE = TODO_ADDED.replace('checkbox "Toggle Todo"', 'checkbox "Toggle Todo" [checked]')


def state(url: str, aria: str, query: str | None = None) -> ObservedState:
    return ObservedState(url=url, query=query, title="t", aria_excerpt=aria, captured_at=datetime.now(UTC))


def test_typing_records_the_field_value() -> None:
    target = Target(role="textbox", name="What needs to be done?")

    change = observed_change(
        state("/todomvc/", TODO_EMPTY),
        state("/todomvc/", TODO_TYPED),
        Action(type="fill", value="Buy milk"),
        target,
    )

    assert change is not None
    assert change.model_dump(exclude_none=True) == {
        "field_values": [{"role": "textbox", "name": "What needs to be done?", "value": "Buy milk"}]
    }


def test_pressing_enter_records_what_appeared() -> None:
    # The spike's TodoMVC run: the plan guessed a list item named "Buy milk" and an input that goes away.
    change = observed_change(
        state("/todomvc/", TODO_TYPED),
        state("/todomvc/", TODO_ADDED),
        Action(type="press", value="Enter"),
        Target(role="textbox", name="What needs to be done?"),
    )

    assert change is not None
    assert change.visible is not None
    assert [(v.role, v.name) for v in change.visible] == [
        ("status", "1 item left"),
        ("button", "Delete"),
        ("checkbox", "Toggle Todo"),
    ]
    assert change.url_matches is None and change.absent is None


def test_ticking_a_checkbox_records_it_checked() -> None:
    target = Target(role="checkbox", name="Toggle Todo")

    change = observed_change(state("/", TODO_ADDED), state("/", TODO_DONE), Action(type="click"), target)

    assert change is not None and change.checked is not None
    assert [(c.role, c.name) for c in change.checked] == [("checkbox", "Toggle Todo")]


def test_a_new_page_records_its_path_without_the_query() -> None:
    change = observed_change(
        state("/", '- heading "Home"'),
        state("/wiki/Alan_Turing", '- heading "Alan Turing"', query="session=8f2a"),
        Action(type="click"),
        Target(role="link", name="Alan Turing"),
    )

    assert change is not None
    assert change.url_matches == "^/wiki/Alan_Turing$"
    assert change.visible and change.visible[0].name == "Alan Turing"
    assert change.absent and change.absent[0].name == "Home"


def test_a_search_on_the_same_path_records_the_query() -> None:
    change = observed_change(
        state("/search", '- heading "Search"'),
        state("/search", '- heading "Search"', query="query=Bengaluru"),
        Action(type="click"),
        Target(role="button", name="Go"),
    )

    assert change is not None and change.url_matches == r"^/search\?query=Bengaluru$"


def test_nothing_changed_gives_none() -> None:
    same = state("/", TODO_ADDED)
    assert observed_change(same, same, Action(type="click"), Target(role="button", name="Delete")) is None


def test_the_recorded_state_verifies_the_page_it_came_from() -> None:
    # A replay checks a step against what really happened: the change must pass the normal verifier.
    after = state("/search", TODO_ADDED, query="q=milk")
    change = observed_change(
        state("/search", TODO_TYPED), after, Action(type="press", value="Enter"), Target(role="textbox")
    )

    assert change is not None
    assert RuleVerifier().verify(change, after).verified
    assert not RuleVerifier().verify(change, state("/search", TODO_TYPED)).verified
    assert isinstance(change, ExpectedState)
