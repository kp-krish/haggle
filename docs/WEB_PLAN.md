# Haggle Web — Implementation Plan

A Next.js website alongside the Discord bot. The website lists, browses and starts deals;
**everything after "start haggling" stays in Discord** (agent chat, confirmations, pickup
time and place, reminders, handoff).

## Decisions (2026-10-24)

| Topic | Choice |
|---|---|
| Hosting | AWS Amplify Hosting, us-east-2 (same account and region as the backend) |
| Login | Discord OAuth via Auth.js; only members of the Haggle server may sign in |
| Budget on the website | A range: **min** = where the buyer's agent opens (public anyway, it's the first offer), **max** = secret ceiling, KMS-encrypted exactly like `/want` |
| Repo | Same repo, `web/` folder |
| Anonymity | Listings show the seller's badges, never their name; names are revealed in Discord after both confirm, as today |
| Look | Plain and quiet: white background, one accent colour, photo-first cards, no gradients, sparkles, chatbot styling or "AI" wording |

## Architecture

```
Browser ── Next.js (Amplify, SSR) ──HMAC-signed──▶ API Gateway /web/* ──▶ web_api Lambda
   │            │ Auth.js session (Discord)                                  │
   │            └─ never holds AWS keys or limits                            ├─ DynamoDB / KMS Encrypt
   └── direct photo upload to S3 (presigned POST)                            └─ listing agent (async)
                                                                                 └─ Step Functions (Discord negotiation)
```

- **Python stays the backend.** A new `web_api` Lambda in the SAM stack reuses `store`,
  `strategy`, the listing agent and the negotiation workflow. Business rules live in one
  place for both Discord and web.
- **Next.js talks to it server-to-server.** Requests are signed with a shared secret and
  carry the signed-in Discord user id, so the browser can never act as someone else.
- **Limits are encrypted inside the Lambda** the moment they arrive; the Next.js server
  forwards the form and keeps nothing.
- **Photos** go straight from the browser to S3 with a presigned upload; pages show them
  with short-lived presigned URLs.

## Flows

1. **Browse** — all open listings (from Discord or web), search, filter by category and
   area, sort by newest/price. Each card: photo, title, asking price, area, seller badges.
2. **Interested** — on a listing: min, max, free times, style. Creates a want tied to that
   listing (no matcher), creates the deal and starts the negotiation. The buyer gets a
   Discord DM: "Haggling for X started from the website; follow along here."
3. **Sell** — photo, description, asking price, area, lowest price, free times, style.
   The listing agent writes the listing; the seller previews it on the site and
   publishes. Published listings also appear in `#listings`.
4. **My Haggle** — your listings, interests and deals with live status (negotiating,
   confirming, pickup Thu 4:30 pm at …), and a Stop button for listings and interests.
5. **Profile** — your badges and pickup history, default free times and style.

## Badges

Computed from the counts the bot already records (split by role):

| Badge | Rule |
|---|---|
| New | No completed pickups yet |
| Reliable seller / buyer | 3+ completed pickups in that role, no no-shows |
| Trusted | 10+ completed pickups, no-show rate under 5% |
| (none / hidden) | 2+ no-shows: no badge, and paused at 3 as today |

## Phases

### W1 — Backend web API (Python, SAM) ✅
- `web_api.py` behind `ANY /web/{proxy+}` on the existing HTTP API; HMAC request
  signing with a secret in Secrets Manager.
- Routes: list/search listings, listing detail, presigned upload, create/preview/
  publish/discard listing, express interest, my items, stop, profile.
- `Listings.by_status` GSI for browsing.
- Listing agent: photos from S3 (web) as well as Discord; new `interest` job (parse
  windows, create want + deal, start workflow).
- Strategy: optional explicit opening offer (the range's min).
- Per-role pickup counters and `badges.py`.
- Tests for every route, including signature checks and "can't act as someone else".

### W2 — Next.js scaffold (`web/`) ✅
- Next.js (App Router, TypeScript), Tailwind, Auth.js Discord provider with
  `identify guilds.members.read`, sign-in rejected for non-members.
- Server-only API client that signs requests; design tokens; layout and nav.

### W3 — Pages ✅
- Browse, listing detail + interest form, sell flow (upload → preview → publish),
  My Haggle, profile. Responsive, accessible, fast on phones.

### W4 — Amplify hosting
- Amplify app connected to the GitHub repo (`web/` as the app root), env vars,
  Discord OAuth redirect URL. Optional custom domain.

### W5 — Polish
- Empty and error states, loading skeletons, end-to-end smoke test of
  "list on web → interested on web → haggle in Discord → confirm".

## What you'll need to do

1. **Discord portal → OAuth2:** add the redirect URL (given at W2/W4) and copy the
   **Client Secret** into `.env` as `DISCORD_CLIENT_SECRET`.
2. **Amplify ↔ GitHub (W4):** authorize the AWS Amplify GitHub app on `kp-krish/haggle`
   in the Amplify console (one click flow), or let me use your `gh` token for it.
