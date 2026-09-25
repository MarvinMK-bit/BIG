"""Export mark schemes from the database into the repository's scheme directory.

Usage (from the backend directory):
    python -m scripts.export_schemes [--out DIR] [--version NAME@VERSION | --all] [--force]

Without --version every database scheme is exported. Each file is named after the
scheme (slugified) and holds the stored YAML verbatim under a provenance header.
The database comes from DATABASE_URL, so an exported DATABASE_URL (overriding .env)
points it at production.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.core.database import AsyncSessionLocal, engine
from app.models.mark_scheme import MarkSchemeRecord
from app.repositories.scheme_repo import MarkSchemeRepository
from app.services.grading.scheme_export import export_filename, export_text
from app.services.grading.schemes import load_scheme

# The directory the backend loads repo schemes from (MARK_SCHEMES_DIR's default)
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "mark_schemes"
_SCHEME_SUFFIXES = (".yaml", ".yml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export BIG mark schemes from the database.")
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help=f"directory to write to (default {DEFAULT_OUT})"
    )
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--version", metavar="NAME@VERSION", help="export only this scheme")
    which.add_argument("--all", action="store_true", help="export every scheme (the default)")
    parser.add_argument("--force", action="store_true", help="overwrite files that already exist")
    return parser.parse_args()


def existing_versions(directory: Path) -> dict[str, Path]:
    """name@version of every readable scheme file already in the directory."""
    found: dict[str, Path] = {}
    if not directory.is_dir():
        return found
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix in _SCHEME_SUFFIXES:
            try:
                found[load_scheme(path).scheme_version] = path
            except ValueError:
                continue  # Not ours to judge here; the backend reports broken files at load
    return found


def export(records: list[MarkSchemeRecord], out: Path, force: bool) -> tuple[int, int]:
    """Write each record's file. Returns (written, skipped)."""
    out.mkdir(parents=True, exist_ok=True)
    on_disk = existing_versions(out)
    exported_on = datetime.now(UTC).date()
    written_this_run: dict[Path, str] = {}
    written = skipped = 0

    for record in records:
        version = record.scheme_version
        target = out / export_filename(record.name)

        reason: str | None = None
        if target in written_this_run:
            reason = f"{target.name} was already written for {written_this_run[target]} in this run"
        elif version in on_disk and on_disk[version] != target:
            # A second file with the same name@version would stop the backend loading schemes
            reason = f"already in the repository as {on_disk[version].name}"
        elif target.exists() and not force:
            reason = f"{target} already exists (use --force to overwrite)"

        if reason is not None:
            print(f"Skipped {version}: {reason}")
            skipped += 1
            continue

        target.write_text(export_text(record, exported_on), encoding="utf-8")
        written_this_run[target] = version
        print(f"Wrote {version} -> {target}")
        written += 1

    return written, skipped


async def main() -> int:
    args = parse_args()
    try:
        async with AsyncSessionLocal() as session:
            repo = MarkSchemeRepository(session)
            if args.version:
                record = await repo.get_by_version(args.version)
                if record is None:
                    print(f"No database scheme {args.version!r}.", file=sys.stderr)
                    return 1
                records = [record]
            else:
                records = await repo.list_everything()
    finally:
        await engine.dispose()

    if not records:
        print("No schemes in the database.")
        return 0
    written, skipped = export(records, args.out, args.force)
    print(f"{written} written, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
