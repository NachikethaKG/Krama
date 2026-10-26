from pathlib import Path

from app.verifier import parse_aria_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_roles_names_values_and_attributes() -> None:
    snapshot = "\n".join(
        [
            '- main "New Repository":',
            '  - heading "New Repository" [level=3]',
            "  - paragraph: The repository name is already used.",
            '  - textbox "Repository Name *": demo-repo',
            '  - checkbox "Initialize Repository" [checked]',
            '  - checkbox "Make repository private"',
            '  - checkbox "Mixed" [checked=mixed]',
            '  - link "Migrate repository.":',
            "    - /url: /repo/migrate",
            '  - button "Say \\"hi\\""',
        ]
    )

    nodes = parse_aria_snapshot(snapshot)

    assert [n.role for n in nodes] == [
        "main", "heading", "paragraph", "textbox", "checkbox", "checkbox", "checkbox", "link", "button"
    ]  # fmt: skip
    heading, paragraph, textbox, checked, unchecked, mixed = nodes[1:7]
    assert heading.attrs == {"level": "3"}
    assert paragraph.name == "" and paragraph.label() == "The repository name is already used."
    assert textbox.name == "Repository Name *" and textbox.value == "demo-repo"
    assert checked.checked and not unchecked.checked and not mixed.checked
    assert nodes[-1].name == 'Say "hi"'


def test_parses_every_real_gitea_snapshot() -> None:
    for f in FIXTURES.glob("*.aria.yaml"):
        nodes = parse_aria_snapshot(f.read_text(encoding="utf-8"))
        assert nodes, f.name
        assert nodes[0].role == "main"
        assert not any(n.role.startswith("/") for n in nodes)


def test_a_field_value_on_the_next_line_is_the_fields_value() -> None:
    # #89: GitHub's issue title "Bug: fix login" needs YAML quoting, so Playwright writes it as a child line.
    nodes = parse_aria_snapshot('- textbox "Add a title":\n  - text: "Bug: fix login"\n- button "Create"')

    assert nodes[0].role == "textbox" and nodes[0].value == "Bug: fix login"
    assert nodes[-1].name == "Create"


def test_quoted_values_are_unquoted() -> None:
    nodes = parse_aria_snapshot("- 'combobox \"Color: #714802\"': \"#714802\"\n- textbox \"Name\": 'it''s'")

    assert [n.value for n in nodes] == ["#714802", "it's"]


def test_a_text_line_under_a_non_field_is_not_taken_as_its_value() -> None:
    nodes = parse_aria_snapshot('- dialog "Edit":\n  - text: Description')

    assert nodes[0].value == "" and nodes[1].role == "text"


def test_a_quoted_key_is_read_too() -> None:
    nodes = parse_aria_snapshot("- 'button \"Choose visibility: Public\"': Public")

    assert nodes[0].role == "button" and nodes[0].name == "Choose visibility: Public"
    assert nodes[0].value == "Public"
