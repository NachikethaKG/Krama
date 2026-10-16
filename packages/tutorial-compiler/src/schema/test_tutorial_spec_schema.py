"""Validation tests for canonical tutorial-spec.schema.json and fixtures."""

import json
from pathlib import Path
import unittest
from jsonschema import Draft7Validator, ValidationError

SCHEMA_PATH = Path(__file__).parent / "tutorial-spec.schema.json"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tutorial-spec.fixture.json"


class TestTutorialSpecSchema(unittest.TestCase):
    def setUp(self) -> None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.schema = json.load(f)
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_tutorial_spec_schema_is_valid_draft7(self) -> None:
        """The canonical schema conforms to JSON Schema Draft-07 specification."""
        Draft7Validator.check_schema(self.schema)
        self.assertEqual(self.schema["$schema"], "http://json-schema.org/draft-07/schema#")
        self.assertEqual(self.schema["$id"], "tutorial-spec.schema.json")

    def test_canonical_fixture_validates_successfully(self) -> None:
        """The realistic Gitea tutorial fixture passes schema validation."""
        validator = Draft7Validator(self.schema)
        errors = list(validator.iter_errors(self.fixture))
        self.assertEqual(len(errors), 0, f"Validation errors found: {[e.message for e in errors]}")

    def test_missing_required_property_fails_validation(self) -> None:
        """Omitting top-level required properties triggers validation failure."""
        validator = Draft7Validator(self.schema)
        invalid_data = dict(self.fixture)
        del invalid_data["scenes"]

        with self.assertRaises(ValidationError) as ctx:
            validator.validate(invalid_data)
        self.assertIn("'scenes' is a required property", str(ctx.exception))

    def test_missing_scene_camera_fails_validation(self) -> None:
        """Scenes without required camera keyframe trigger validation failure."""
        validator = Draft7Validator(self.schema)
        invalid_data = json.loads(json.dumps(self.fixture))
        del invalid_data["scenes"][0]["camera"]

        with self.assertRaises(ValidationError) as ctx:
            validator.validate(invalid_data)
        self.assertIn("'camera' is a required property", str(ctx.exception))

    def test_invalid_click_type_fails_validation(self) -> None:
        """Unknown click types fail enum validation."""
        validator = Draft7Validator(self.schema)
        invalid_data = json.loads(json.dumps(self.fixture))
        invalid_data["scenes"][0]["cursor"]["click_type"] = "triple_click"

        with self.assertRaises(ValidationError) as ctx:
            validator.validate(invalid_data)
        self.assertIn("is not one of ['single', 'double', 'none']", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
