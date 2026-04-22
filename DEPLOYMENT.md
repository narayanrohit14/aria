# ARIA Deployment

## 1. First-time Railway setup

Install and authenticate the Railway CLI:

```bash
railway login
```

Initialize the repo against Railway. You can either create a new project or link to an existing one:

```bash
railway init
```

Add the managed Postgres plugin:

```bash
railway add
```

Choose the Postgres plugin when prompted.

Add the managed Redis plugin:

```bash
railway add
```

Choose the Redis plugin when prompted.

To get the `RAILWAY_TOKEN` for GitHub Actions:

1. Open the Railway dashboard.
2. Go to your account settings or project token settings.
3. Create a new token with deployment access.
4. Add it to GitHub as the `RAILWAY_TOKEN` repository secret.

## 2. Environment variables to set in Railway

Variables from `.env.example`:

- `LIVEKIT_URL`: set manually
- `LIVEKIT_API_KEY`: set manually
- `LIVEKIT_API_SECRET`: set manually
- `OPENAI_API_KEY`: set manually
- `CARTESIA_API_KEY`: set manually
- `ASSEMBLYAI_API_KEY`: set manually
- `POSTGRES_URL`: Railway may provide `DATABASE_URL` automatically from the Postgres plugin; map or duplicate it into `POSTGRES_URL` for the API service
- `REDIS_URL`: Railway may provide this automatically from the Redis plugin
- `ARIA_ENV`: set manually, usually `production`
- `LOG_LEVEL`: set manually, usually `INFO`
- `ARIA_API_URL`: set manually for the frontend, using your deployed API URL

Recommended additional note:

- If Railway only provides `DATABASE_URL`, create `POSTGRES_URL=${{DATABASE_URL}}` or its Railway dashboard equivalent for compatibility with the current backend config.

## 3. Manual deployment

Before CI is wired end-to-end, you can deploy each service manually:

```bash
railway up --service aria-api
railway up --service aria-frontend
```

## 4. Verifying deployment

Inspect API logs:

```bash
railway logs --service aria-api
```

Verify health from the deployed API:

```bash
curl https://your-api.railway.app/health
```

You should get a JSON response with at least:

- `status`
- `version`
- `environment`
- `model_loaded`
- `database_connected`

## 5. Custom domain setup (optional)

To add a custom domain:

1. Open the Railway dashboard.
2. Select the service you want to expose.
3. Go to the networking or domains section.
4. Add your custom domain.
5. Create the required DNS records at your DNS provider.
6. Wait for Railway to validate the domain and issue TLS certificates.
