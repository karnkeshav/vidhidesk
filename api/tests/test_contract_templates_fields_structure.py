"""CONTRACTS-001: the five affected intake schemas must use the
application's "fields" array structure (IntakeSchema/IntakeField in
web/src/lib/api.ts, consumed server-side via schema.get("fields", [])
in app/services/contracts.py), not raw JSON Schema properties/required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACTS_TEMPLATES_DIR = REPO_ROOT / "templates" / "contracts"

AFFECTED_SCHEMA_FILES = [
    "agreement-to-sell.schema.json",
    "joint-venture.schema.json",
    "lease-deed.schema.json",
    "leave-licence.schema.json",
    "software-dev.schema.json",
]

_ALLOWED_FIELD_TYPES = {"text", "textarea", "select", "boolean", "date", "list"}


def _load(filename: str) -> dict:
    return json.loads((CONTRACTS_TEMPLATES_DIR / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_schema_file_is_valid_json(filename: str) -> None:
    schema = _load(filename)
    assert isinstance(schema, dict)


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_schema_has_top_level_fields_array(filename: str) -> None:
    schema = _load(filename)
    assert "fields" in schema
    assert isinstance(schema["fields"], list)
    assert len(schema["fields"]) > 0


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_schema_no_longer_uses_json_schema_properties(filename: str) -> None:
    schema = _load(filename)
    assert "properties" not in schema
    assert "required" not in schema


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_every_field_has_key_type_and_required(filename: str) -> None:
    schema = _load(filename)
    seen_keys = set()
    for field in schema["fields"]:
        assert isinstance(field, dict)
        assert isinstance(field.get("key"), str) and field["key"], field
        assert field["key"] not in seen_keys, f"duplicate field key {field['key']!r}"
        seen_keys.add(field["key"])
        assert isinstance(field.get("label"), str) and field["label"], field
        assert field.get("type") in _ALLOWED_FIELD_TYPES, field
        assert isinstance(field.get("required"), bool), field


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_select_fields_declare_options(filename: str) -> None:
    schema = _load(filename)
    for field in schema["fields"]:
        if field["type"] == "select":
            assert isinstance(field.get("options"), list) and field["options"], field


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_state_field_present_for_state_rules_gating(filename: str) -> None:
    schema = _load(filename)
    keys = {f["key"] for f in schema["fields"]}
    assert "state" in keys


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_groups_reference_only_declared_field_keys(filename: str) -> None:
    schema = _load(filename)
    field_keys = {f["key"] for f in schema["fields"]}
    for group in schema.get("groups", []):
        assert isinstance(group.get("id"), str) and group["id"]
        assert isinstance(group.get("label"), str) and group["label"]
        assert isinstance(group.get("field_keys"), list) and group["field_keys"]
        for key in group["field_keys"]:
            assert key in field_keys, f"group {group['id']!r} references unknown field {key!r}"
        assert isinstance(group.get("summary_template"), str) and group["summary_template"]


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_template_key_and_title_present(filename: str) -> None:
    schema = _load(filename)
    assert isinstance(schema.get("template_key"), str) and schema["template_key"]
    assert isinstance(schema.get("title"), str) and schema["title"]


@pytest.mark.parametrize("filename", AFFECTED_SCHEMA_FILES)
def test_with_schema_defaults_hydrates_without_error(filename: str) -> None:
    """Focused regression for the actual break: app/services/contracts.py's
    _with_schema_defaults does `field["key"]` (a required, not optional,
    lookup) for every entry in schema["fields"] — the JSON-Schema-shaped
    files (a "properties" object, no top-level "fields" list) made this a
    silent no-op instead of a crash, since schema.get("fields", []) just
    returned an empty list and every intake form field rendered blank.
    """
    from app.services.contracts import _with_schema_defaults

    schema = _load(filename)
    result = _with_schema_defaults({}, schema)
    for field in schema["fields"]:
        assert field["key"] in result
