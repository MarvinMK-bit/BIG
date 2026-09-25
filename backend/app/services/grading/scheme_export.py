import re
from datetime import date

from app.models.mark_scheme import MarkSchemeRecord

_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def export_filename(name: str) -> str:
    """The repo file name for a scheme: its name slugified, e.g. "Quadratic (any)" -> "quadratic-any.yaml"."""
    slug = _NON_SLUG_RE.sub("-", name.casefold()).strip("-")
    return f"{slug or 'scheme'}.yaml"


def contributor(record: MarkSchemeRecord) -> str:
    """The owner's username if they opted in to attribution, else "anonymous".

    The record's owner must already be loaded.
    """
    owner = record.owner
    return owner.username if owner is not None and owner.attribution_opt_in else "anonymous"


def export_text(record: MarkSchemeRecord, exported_on: date) -> str:
    """The stored YAML, verbatim, under a header saying where it came from."""
    header = (
        "# Exported from a BIG instance database.\n"
        f"# Contributed by: {contributor(record)}\n"
        f"# Source: {record.source.value}\n"
        f"# Exported: {exported_on.isoformat()}\n"
    )
    return header + record.yaml_content
