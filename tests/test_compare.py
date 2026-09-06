"""
Tests for the spec comparison logic.

Run these with:  pytest
"""

from apidiff.compare import compare


# ---------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------
# Writing out the full OpenAPI nesting in every single test would be
# painful and would bury the part that actually matters. So we write it
# once here, and each test just says which fields it wants.
#
# Building small helpers like this is a normal part of writing tests.
#
# Example:
#     make_spec({"/users": {"id": "integer", "email": "string"}})
#
# ...produces a spec with one endpoint, GET /users, returning those
# two fields.
# ---------------------------------------------------------------------


def make_spec(endpoints):
    """
    Build a minimal but valid OpenAPI spec.

    endpoints: a dict of path -> {field_name: field_type}
    """
    paths = {}
    for path, fields in endpoints.items():
        properties = {}
        for field_name, field_type in fields.items():
            properties[field_name] = {"type": field_type}

        paths[path] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": properties,
                                }
                            }
                        }
                    }
                }
            }
        }

    return {"openapi": "3.0.0", "paths": paths}


def breaking_descriptions(findings):
    """
    Pull just the descriptions of the breaking changes out of a
    findings list, so tests can check what was flagged.

    Remember: compare() returns a list of (is_breaking, description).
    """
    return [finding.message for finding in findings if finding.breaking]


# ---------------------------------------------------------------------
# WORKED EXAMPLE - read this one carefully, it's the pattern
# ---------------------------------------------------------------------


def test_removed_field_is_breaking():
    # ARRANGE - set up the two versions we want to compare.
    old_spec = make_spec({"/users": {"id": "integer", "email": "string"}})
    new_spec = make_spec({"/users": {"id": "integer"}})  # email is gone

    # ACT - run the code we are testing.
    findings = compare(old_spec, new_spec)

    # ASSERT - state what we expect to be true.
    breaking = breaking_descriptions(findings)

    assert len(breaking) == 1
    assert "email" in breaking[0]


def test_added_field_is_safe():
    # Old spec has just "id". New spec has "id" and "signup_date".
    old_spec = make_spec({"/users": {"id": "integer"}})
    new_spec = make_spec({"/users": {"id": "integer", "signup_date": "string"}})
    # Nothing should be flagged as breaking
    findings = compare(old_spec, new_spec)

    # assert that breaking_descriptions(findings) is empty.
    breaking = breaking_descriptions(findings)

    # An empty list is falsy, so `assert not breaking` reads nicely.
    assert not breaking



def test_type_change_is_breaking():
    # Same field name in both specs, but the type changes from
    # "integer" to "string". That should be flagged
    old_spec = make_spec({"/users": {"id": "integer"}})
    new_spec = make_spec({"/users": {"id": "string"}})

    # Hint: check that the description mentions the field name.
    findings = compare(old_spec, new_spec)
    breaking = breaking_descriptions(findings)

    assert len(breaking) == 1
    assert "id" in breaking[0]

def test_removed_endpoint_is_breaking():
    # Old spec has two endpoints, new spec has only one.
    old_spec = make_spec({"/users": {"id": "integer"}, "/health": {}})
    new_spec = make_spec({"/users": {"id": "integer"}})
    # The missing endpoint should be flagged.
    findings = compare(old_spec, new_spec)
    breaking = breaking_descriptions(findings)
    # Hint: make_spec takes multiple paths -
    #   make_spec({"/users": {...}, "/health": {...}})
    make_spec({"/users": {"id": "integer"}, "/health": {}})

    assert len(breaking) == 1
    assert "health" in breaking[0]


def test_identical_specs_produce_no_findings():
    # Compare a spec against itself. There should be no findings
    # at all - not breaking ones, not safe ones.
    old_spec = make_spec({"/users": {"id": "integer"}})
    new_spec = make_spec({"/users": {"id": "integer"}})

    # Hint: this one asserts on `findings` directly, not on
    # breaking_descriptions(findings).
    findings = compare(old_spec, new_spec)
    assert not findings