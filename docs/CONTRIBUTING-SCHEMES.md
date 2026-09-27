# Contributing mark schemes

Mark schemes come from two places:

- **Repository files** in [`backend/mark_schemes/`](../backend/mark_schemes/), loaded by every
  instance of BIG.
- **Uploads** to a running instance, stored in that instance's database.

A scheme uploaded to a hosted instance lives only in that instance's database. It is **not**
automatically added to the repository, so other instances and fresh deployments don't have it.

Questions marked on their working (`matcher: procedure`) must use BIG's mark codes, in order:
see [MARK-CODES.md](MARK-CODES.md).

## Moving an uploaded scheme into the repository

An admin reviews it on the Moderation page, exports it and commits the file.

Every uploaded scheme starts as pending review. On `/moderation` an admin can read it, grade
one of their own scripts with it (a test run, kept out of accuracy figures), and accept or
decline it. Review only decides whether the scheme enters the repository: pending and declined
schemes remain usable for grading by anyone who can see them.

With database access, from the `backend` directory:

```bash
# Every accepted database scheme, into backend/mark_schemes/
python -m scripts.export_schemes

# Also schemes not yet reviewed (declined schemes are never exported)
python -m scripts.export_schemes --include-pending

# One scheme, overwriting an existing file of the same name
python -m scripts.export_schemes --version quadratic-any@0.2.0 --force
```

The script uses `DATABASE_URL`, so `DATABASE_URL=… python -m scripts.export_schemes` exports
from production. It never overwrites a file without `--force`, and it lists what it wrote and
what it skipped. Each scheme written has its `exported_at` recorded in the database.

Without database access, an admin downloads the same file from the hosted instance:

```
GET /api/v1/grading/schemes/{name@version}/export
```

Each file is the uploaded YAML, unchanged, under a header recording that it was exported,
who contributed it, its source and the export date. Review it, then open a pull request that
adds it to `backend/mark_schemes/`. Once the pull request is merged and deployed, the
repository copy is loaded first, so the database copy can be deleted.

## Credit

A contributor is named in the header only if they have opted in to attribution
(`attribution_opt_in` on their account). Otherwise the header says `anonymous`.

## Where this is heading

Eventually, uploading a scheme will open a pull request directly. Exporting by hand is the
interim step until then.
