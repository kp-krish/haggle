# Haggle — Implementation Plan

Source of truth: `Haggle-Architecture.pdf`. This plan turns it into build phases; each
phase ends with something runnable and tested, and is committed separately.

## Ground rules

- **Code picks every number, the model only writes words.** `strategy.py` and
  `scheduler.py` are pure Python with no AWS/Discord imports (simulation mode).
- **A limit lives in one place.** Floor/ceiling are KMS-encrypted in DynamoDB and decrypted
  only in the negotiator Lambda for the owning side. The other side's limit never enters a
  prompt, a log line, a Step Functions payload, or a Discord message.
- **Every commitment waits for a person** (publish, start haggling, confirm deal, done).
- Region **us-east-2**, pinned in `samconfig.toml`. The spec says us-west-2, but the AWS
  organization's SCP denies every region except us-east-2.

## Environment (verified 2026-10-24)

| Item | State |
|---|---|
| AWS | account `908494155046`, IAM user `heatcheck-dev` |
| Bedrock (us-east-2) | `us.anthropic.claude-haiku-4-5-20251001-v1:0` callable (text + images); Haiku 5.5 / Sonnet 5.5 not enabled on this account |
| GitHub | `gh` logged in as `kp-krish` |
| Tooling | SAM CLI 1.170, Docker 29, Python 3.13 local |
| Lambda runtime | Python 3.12 per spec; third-party deps in a shared layer built by `scripts/build_layer.py` (Linux wheels via pip, no Docker) |

## Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Models | Haiku 4.5 for negotiator messages **and** listing (multimodal) | One model, cheap, fast; `TextModelId` / `VisionModelId` parameters to swap |
| Signature check | PyNaCl (Ed25519) | Standard for Discord interactions |
| Deps | `boto3` (in runtime), `pynacl`, `requests`/`urllib3` | Keep Lambda packages small |
| Offer timeout | 2 h (env var), 2 timeouts closes deal | Per spec |
| Campus data | ASU Tempe public spots (Memorial Union, Hayden Library, SDFC, …) | Matches the example in the spec |
| Encryption | KMS `Encrypt`/`Decrypt` on the limit field only; key policy grants Decrypt to the negotiator role only | Interactions handler can encrypt, cannot decrypt |
| Windows parsing | Model turns "weekdays after 3, Sat morning" into JSON ranges; code validates them | Model writes structure, code checks it |

## Phases

### Phase 0 — Repo scaffold
- `git init`, `.gitignore`, `README.md`, layout from the spec, `pyproject.toml`
  (pytest, ruff), `requirements.txt` per function.
- Create GitHub repo `kp-krish/haggle` (private) and push.
- **Done when:** empty `pytest` passes, repo on GitHub.

### Phase 1 — Pure core (no AWS, no Discord)
- `strategy.py`: `seller_offer(t)`, `buyer_offer(t)`, opening offer `O = min(0.6·A, C)`,
  beta per style (patient 0.5 / balanced 1 / quick 2), T = 6, whole-dollar rounding that
  rounds *toward the owner* (seller rounds up, buyer down) so rounding can never cross a
  limit, monotonic concessions, accept rules, `simulate(A, F, C, styles)`.
- `scheduler.py`: window intersection (≥ 20 min slots), earliest slot, spot choice from
  `src/data/places.json` by campus area + curbside for large items, daylight preference.
- `guard.py`: dollar-amount extraction, "only the strategy's number" check, forbidden
  words near numbers (floor / lowest / maximum / …), injection wrapping of the other
  side's text.
- Tests: `test_strategy.py` (property-style sweep over many A/F/C/style pairs → no offer
  crosses a limit, never regresses, deal iff F ≤ C reachable; reproduces the $55 fridge
  example shape), `test_guard.py` (leak + injection cases), `test_scheduler.py`.
- **Done when:** all tests green locally, `python -m src.strategy` replays a negotiation.

### Phase 2 — Infrastructure skeleton (SAM)
- `template.yaml`: HTTP API, interactions Lambda, 6 DynamoDB tables (on demand) with GSIs
  `Listings.by_category`, `Wants.by_category`, `Deals.by_seller` + `Deals.by_buyer` (a deal has two users, so "by user" is one index per side), Streams on Listings/Wants,
  TTL on Offers, S3 photo bucket (lifecycle rule), KMS key, Secrets Manager secret for
  bot token + public key, least-privilege roles per function, CloudWatch alarms, AWS
  Budget ($10 / $25).
- `store.py`: table access + KMS encrypt/decrypt helpers.
- `samconfig.toml` pinned to us-east-2.
- **Done when:** `sam build --use-container && sam deploy` succeeds and the stack is empty
  but healthy.

### Phase 3 — Discord interactions ✅
- `interactions.py`: Ed25519 verification, PING/PONG, deferred replies (3-second rule),
  routing for `/sell`, `/want`, `/deals`, `/stop`, modal submits, button clicks;
  async hand-off (async Lambda invoke or Step Functions `SendTaskSuccess`).
- `notify.py`: DMs, `#listings` posts, follow-up/edit of deferred replies, buttons.
- `scripts/register_commands.py`.
- **You do:** create the Discord application + bot, invite it to a test server, give me
  app ID / public key / bot token (I store them in Secrets Manager, never in git).
- **Done when:** `/deals` answers in the test server.

### Phase 4 — Listing and wants ✅
- `listing_agent.py`: photo from Discord attachment → S3, Bedrock writes title /
  description / category, flags prohibited items; seller previews and taps Publish.
- Modal for floor (+ pickup windows) → encrypted write. `/want` + modal for ceiling.
- **Done when:** a listing appears in `#listings` and both limits are stored encrypted.

### Phase 5 — Matcher ✅
- `matcher.py` on DynamoDB Streams: category + keyword overlap + campus area; DM the buyer
  "Start haggling?". Never uses limits (it can't decrypt them).
- **Done when:** a matching want triggers the buyer prompt.

### Phase 6 — Negotiation workflow ✅
- `statemachine/negotiation.asl.json` (Standard): buyer opens → alternate turns → accept /
  counter / rounds exhausted → schedule → both confirm (task tokens, 2 h timeouts, two
  timeouts close) → reveal identities → reminders.
- `negotiator.py`: loads only its own side, decrypts own limit, asks `strategy` for the
  number, asks Bedrock for the text, runs `guard` (one rewrite → template fallback),
  writes Offer, mirrors the transcript to both DMs.
- Multiple buyers per listing; first double-confirm wins, others close "item sold".
  Stop button and mid-deal limit change (applies next round).
- **Done when:** two test accounts complete the fridge-style negotiation end to end.

### Phase 7 — Scheduling, reminders, handoff ✅
- Scheduler step + conflict loop (ask each side for one more window, release after 2).
- EventBridge Scheduler reminder 1 h before pickup with "Running late"; post-pickup
  Done / Didn't happen buttons; no-show reopens listing; reliability count on Users.
- **Done when:** a confirmed deal gets a reminder and a handoff prompt.

### Phase 8 — Hardening ✅
- **Final-round leak (fixed):** the spec's curve made each agent's round-6 offer
  exactly its limit. Agents now hold back a hidden 5-20% reserve derived from their
  own ciphertext, and accept anything within the limit in the final rounds; the
  final ask covers near misses.
- **Red team (done):** `scripts/redteam.py` sends 7 injection attacks to the live
  seller agent; 0 leaks. It also caught the seller voicing buyer lines, now fixed.
- **Logs (checked):** every log line carries ids only; workflow history carries ids
  and public offers.
- **Alerts (checked):** SNS email subscription confirmed; test alarm delivered.
- Optional private "last round coming up" nudge to both sides.
- Red-team tests through the real negotiator (injection prompts, "what's your floor?").
- Logs scrubbed of limits; alarms on failed executions; budget alerts verified.
- README: deploy steps, Discord setup, simulation mode.

## Out of scope for v1
Payments (never), school-email verification bot (use server join rules), web UI.

## What I need from you before Phase 3
1. Discord application + bot (app ID, public key, bot token) and a test server.
2. Two Discord accounts to play seller and buyer.
