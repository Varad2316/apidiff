"""
Core comparison logic.

Everything here is a plain function that takes dictionaries and returns
data. Nothing prints and nothing exits. That is deliberate: it keeps
this module easy to test, and pushes all the input/output concerns into
cli.py where they belong.
"""

from dataclasses import dataclass


@dataclass
class Finding:
    """
    One difference between two specs.

    Using a small class instead of a plain tuple means tests can say
    finding.breaking instead of finding[0], which is much easier to read
    when a test fails at 1am.
    """

    breaking: bool
    message: str

    def __str__(self):
        marker = "x" if self.breaking else "."
        return f"{marker} {self.message}"


def get_endpoints(spec):
    """
    Flatten the spec into {"GET /users/{id}": operation_dict}.

    An OpenAPI spec nests paths inside methods:
        paths -> "/users/{id}" -> "get" -> {...}
    This turns that into something flat enough to compare with a loop.
    """
    endpoints = {}
    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            endpoints[f"{method.upper()} {path}"] = operation
    return endpoints


def get_response_fields(operation):
    """
    Return {field_name: type} for this endpoint's 200 response.

    The chained .get() calls with {} defaults mean a missing layer gives
    an empty dict rather than a crash. Real specs are inconsistent, so
    this matters more than it looks like it should.
    """
    schema = (
        operation.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )

    fields = {}
    for name, info in schema.get("properties", {}).items():
        fields[name] = info.get("type", "unknown")
    return fields


def compare_endpoints(old_spec, new_spec):
    """Check for endpoints that were added or removed."""
    findings = []
    old = get_endpoints(old_spec)
    new = get_endpoints(new_spec)

    # An endpoint that existed and is now gone is breaking: any client
    # still calling it gets a 404.
    for name in old:
        if name not in new:
            findings.append(Finding(True, f"Endpoint removed: {name}"))

    # A brand new endpoint is safe. Nobody was calling something that
    # did not exist yesterday.
    for name in new:
        if name not in old:
            findings.append(Finding(False, f"Endpoint added: {name}"))

    return findings


def compare_response_fields(old_spec, new_spec):
    """Check response fields on endpoints present in both specs."""
    findings = []
    old = get_endpoints(old_spec)
    new = get_endpoints(new_spec)

    for name in old:
        if name not in new:
            continue  # already reported by compare_endpoints

        old_fields = get_response_fields(old[name])
        new_fields = get_response_fields(new[name])

        for field, old_type in old_fields.items():
            # A removed field is breaking: client code reading it now
            # gets nothing back.
            if field not in new_fields:
                findings.append(
                    Finding(True, f"Field removed: {name} -> '{field}'")
                )
                continue

            # A changed type is breaking: a client expecting a number
            # and receiving text will likely crash.
            new_type = new_fields[field]
            if old_type != new_type:
                findings.append(
                    Finding(
                        True,
                        f"Type changed: {name} -> '{field}' "
                        f"was {old_type}, now {new_type}",
                    )
                )

        # A newly added field is safe.
        for field in new_fields:
            if field not in old_fields:
                findings.append(
                    Finding(False, f"Field added: {name} -> '{field}'")
                )

    return findings


def compare(old_spec, new_spec):
    """
    Run every check and return a combined list of Findings.

    New rule categories get added here as their own function, so this
    stays a short list of what the tool knows how to check.
    """
    findings = []
    findings.extend(compare_endpoints(old_spec, new_spec))
    findings.extend(compare_response_fields(old_spec, new_spec))
    return findings


def has_breaking(findings):
    """True if any finding is breaking. Used to decide the exit code."""
    return any(f.breaking for f in findings)