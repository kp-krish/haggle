# Haggle web

The website for Haggle: browse, sell and start deals. Negotiation, confirmations and
pickup details stay in Discord.

- Next.js 16 (App Router), Tailwind CSS 4, Auth.js (Discord) — see `AGENTS.md`: this
  Next.js version differs from older docs; the bundled docs are in
  `node_modules/next/dist/docs/`.
- Talks only to the backend's website API (`src/web_api.py`) from the server, signing
  each request with `HAGGLE_HMAC_SECRET` (`src/lib/api.ts`). The browser never sees the
  secret, AWS credentials or anyone's limits.
- Only members of the Haggle Discord server can sign in (`src/auth.ts`).

## Run locally

```powershell
# from the repo root: writes web/.env.local from the deployed stack and ../.env
.\.venv\Scripts\python scripts\web_env.py

cd web
npm install
npm run dev        # http://localhost:3000
```

Needs `DISCORD_CLIENT_SECRET` in the root `.env`, and
`http://localhost:3000/api/auth/callback/discord` added under **OAuth2 > Redirects** in
the Discord developer portal.

## Layout

```
src/auth.ts                 Discord sign-in, server-membership check
src/lib/api.ts              signed server-to-server calls to the backend
src/app/page.tsx            intro (signed out) / browse (signed in)
src/app/listings/[id]/      listing, seller preview and publish, buyer interest form
src/app/sell/               photo upload straight to S3, then the listing form
src/app/me/                 my listings, deals, badges; defaults in me/settings
src/app/actions.ts          server actions (each re-checks the session)
src/components/             UI kit: price tag, pills, buttons, fields
```
