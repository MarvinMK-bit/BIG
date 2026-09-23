# Deploying BIG

BIG runs as two Render web services, defined in [`render.yaml`](../render.yaml), plus a Neon
Postgres database:

- **big-backend**: FastAPI. Runs database migrations on every start.
- **big-frontend**: Next.js. The browser only talks to this service. It forwards API calls to
  the backend server-side and keeps the login token in an httpOnly cookie.

Everything below runs on free tiers. No secret goes into the repository: every secret is
entered in the Render dashboard.

> **Uploaded files do not persist.** Render's free instances have no persistent disk. Uploaded
> scripts and marking guide photos are saved to `/tmp/uploads`, which is wiped on every
> restart, every deploy, and every time the service goes to sleep after 15 idle minutes. The
> database keeps everything else: sessions, extracted text, grades and mark schemes. But the
> original image or PDF is gone, so a session that wasn't extracted before a restart can never
> be extracted. Extract straight after uploading.

## 1. Create the Neon database

1. Sign in at [console.neon.tech](https://console.neon.tech) and create a project. Choose the
   **AWS Europe Central 1 (Frankfurt)** region so it sits next to the Render services.
2. Open the project's **Connect** dialog, pick the default branch and database, and **turn off
   connection pooling**. The pooled host (the one with `-pooler` in its name) runs PgBouncer in
   transaction mode, which breaks the prepared statements the asyncpg driver uses.
3. Copy the connection string. It looks like this:

   ```
   postgresql://neondb_owner:PASSWORD@ep-example-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

### Convert it to the asyncpg form

The backend uses SQLAlchemy's async engine with the asyncpg driver, which needs a different
scheme and doesn't understand libpq's `sslmode` or `channel_binding` parameters. Make three
changes:

1. Change `postgresql://` to `postgresql+asyncpg://`.
2. Change `sslmode=require` to `ssl=require`.
3. Delete `&channel_binding=require`.

The example above becomes:

```
postgresql+asyncpg://neondb_owner:PASSWORD@ep-example-123456.eu-central-1.aws.neon.tech/neondb?ssl=require
```

This is your `DATABASE_URL`. If you ever set your own password containing characters like `@`,
`/` or `:`, percent-encode them. Neon's generated passwords don't need this.

## 2. Generate the secret key

`SECRET_KEY` signs login tokens. Generate a fresh one for production and don't reuse it
anywhere else:

```sh
openssl rand -hex 32
```

## 3. Create both Render services from the Blueprint

1. Push the repository to GitHub.
2. In the [Render dashboard](https://dashboard.render.com), choose **New → Blueprint** and
   connect the repository. Render reads `render.yaml` and lists `big-backend` and
   `big-frontend`.
3. Render asks for every variable marked `sync: false`. Fill them in as below. Everything else
   is already set in `render.yaml`.

### Backend (`big-backend`)

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | The converted `postgresql+asyncpg://…?ssl=require` string from step 1 |
| `SECRET_KEY` | The output of `openssl rand -hex 32` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key. Required: `OCR_ENGINE` is `claude`, and the LLM grader uses it too. Every OCR and LLM grading call is billed to this key. |
| `ALLOWED_ORIGINS` | The frontend's URL, e.g. `https://big-frontend.onrender.com`. Comma-separate several. `*` is rejected at startup. |

Set in `render.yaml`, no action needed: `ALLOW_REGISTRATION=false`, `DEBUG=false`,
`OCR_ENGINE=claude`, `STORAGE_LOCAL_ROOT=/tmp/uploads`, `PYTHON_VERSION=3.12.3`.

### Frontend (`big-frontend`)

| Variable | Value |
| --- | --- |
| `BACKEND_URL` | The backend's URL with no path and no trailing slash, e.g. `https://big-backend.onrender.com`. The frontend adds `/api/v1` itself. |

`NODE_ENV=production` is set in `render.yaml`. It also turns on the `Secure` flag on the login
cookie, so the cookie is only ever sent over HTTPS.

### Service URLs

Render names each service `https://<name>.onrender.com`, but adds a suffix if the name is
already taken. After the first deploy, check both URLs on each service's page. If either
differs from what you entered, fix `ALLOWED_ORIGINS` or `BACKEND_URL` under
**Environment** and redeploy that service.

### Check the deploy

The backend's start command runs `alembic upgrade head` before starting the server, so the
first deploy creates every table. Then:

```sh
curl https://big-backend.onrender.com/health
# {"status":"ok"}
```

`/health` never touches the database, so Render's health checks and the keep-alive pings don't
wake Neon's compute.

## 4. Create the first admin

Registration is off (`ALLOW_REGISTRATION=false`), so the first account is created with the CLI
in `backend/scripts/create_user.py`. It prompts for the password so it never shows up in shell
history.

### From your own machine (free tier)

Render Shell is not available on free instances, so run the CLI locally against the Neon
database. Environment variables take precedence over any local `backend/.env`.

```sh
cd backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Paste the asyncpg DATABASE_URL when prompted; `read -s` keeps it out of shell history
read -rs DATABASE_URL && export DATABASE_URL
export SECRET_KEY=unused-for-this-command

python -m scripts.create_user --username YOUR_NAME --email you@example.com --admin
```

`SECRET_KEY` has to be set for the settings to load, but creating a user doesn't use it.

### From Render Shell (paid instances)

On a paid instance type, open **big-backend → Shell**. The environment is already set:

```sh
python -m scripts.create_user --username YOUR_NAME --email you@example.com --admin
```

Then sign in on the frontend URL.

## 5. Set up the keep-alive workflow

Free Render services sleep after 15 minutes without traffic, and the next visitor waits
through a cold start of up to a minute. [`.github/workflows/keep-alive.yml`](../.github/workflows/keep-alive.yml)
pings both services every 14 minutes between 05:00 and 15:00 UTC (08:00–18:00 East Africa
Time).

The window exists because free instance hours are capped at 750 per month, shared across both
services. Keeping both awake all day would need about 1,488 hours. The window uses about 635,
which leaves room for use outside it. Outside the window, services sleep and wake on the first
request.

The workflow reads its URLs from two repository variables, so none are hardcoded. In the GitHub
repository, go to **Settings → Secrets and variables → Actions → Variables → New repository
variable**, and add:

| Variable | Value |
| --- | --- |
| `BACKEND_HEALTH_URL` | `https://big-backend.onrender.com/health` |
| `FRONTEND_URL` | `https://big-frontend.onrender.com/` |

Or with the GitHub CLI:

```sh
gh variable set BACKEND_HEALTH_URL --body "https://big-backend.onrender.com/health"
gh variable set FRONTEND_URL --body "https://big-frontend.onrender.com/"
```

To test it, open **Actions → Keep Render services awake → Run workflow**. Both steps should
pass.

Scheduled workflows only run from the default branch. GitHub also disables them in public
repositories after 60 days without activity, and re-enabling is one click on the Actions page.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Backend fails at startup with `unexpected keyword argument 'sslmode'` or `'channel_binding'` | `DATABASE_URL` still has libpq parameters. See [Convert it to the asyncpg form](#convert-it-to-the-asyncpg-form). |
| `prepared statement "…" does not exist` | `DATABASE_URL` points at Neon's pooled (`-pooler`) host. Use the direct connection string. |
| Backend fails at startup mentioning `ALLOWED_ORIGINS` | It contains `*`. List exact origins instead. |
| Login shows "Backend unavailable" | `BACKEND_URL` is wrong, or the backend is still starting. Open its `/health` URL, wait for it, and retry. |
| Extraction fails with `No stored file for key …` | The upload was lost in a restart. Upload the script again. See the warning at the top. |
