# Haggle

Agents that bargain for you. Every student gets a personal agent in Discord that lists,
finds, bargains and schedules pickups, while each student's price limit stays secret from
the other side.

- **Code picks every number; the model only writes the words.**
- Serverless on AWS (us-east-2): API Gateway, Lambda (Python 3.12), Step Functions,
  DynamoDB + KMS, S3, Bedrock, EventBridge Scheduler.

`Haggle-Architecture.pdf` is the design; [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)
tracks what was built and where it differs.

## How a deal works

1. **`/sell`** with a photo: the listing agent (Bedrock, vision) writes the listing and
   flags prohibited items. A private form takes the floor price, free times and style.
   The seller previews and publishes to `#listings`.
2. **`/want`**: a private form takes the max price, free times and style.
3. **Match**: when a listing and a want open, the matcher (DynamoDB Streams) compares
   category and words and DMs the buyer *Start haggling?*
4. **Haggle**: one Step Functions workflow per deal. The seller's and buyer's negotiators
   take turns; `strategy.py` picks every price, Bedrock words it, `guard.py` blocks any
   other number or limit talk. Both students watch the transcript in their DMs and can
   stop or change their limit at any time.
5. **Final ask**: if rounds run out, the buyer's agent privately asks its student about
   the seller's final offer when it is within reach.
6. **Pickup**: `scheduler.py` picks the earliest slot in both students' free times and the
   nearest public spot (curbside for large items). No overlap: each side is asked for one
   more time, twice, then the deal is released.
7. **Confirm**: both students confirm privately. First confirmed deal wins the item;
   other buyers hear "item sold". Names are revealed only now.
8. **Follow-up**: a reminder an hour before (with *Running late*), then *Done* /
   *Didn't happen*. A no-show relists the item and re-offers it to earlier buyers; three
   no-shows pause a student. Payment happens in person; Haggle never handles money.

## Privacy model

| What | Who can read it |
|---|---|
| Seller's floor | Encrypted with KMS. Only the **seller's** negotiator role may decrypt (`kms:EncryptionContext:record = listing#*`). |
| Buyer's max | Encrypted with KMS. Only the **buyer's** negotiator role may decrypt (`want#*`). |
| Free times | Stored per side; the other side only ever sees the chosen slot. |
| Identities | Revealed only after both students confirm. |

- The other side's limit is never in a prompt, so the model cannot reveal it. Text from
  the other side is quoted as data (`guard.wrap_untrusted`).
- Agents keep a hidden reserve (5-20% of their range, derived from their own ciphertext),
  so the final offer is not the limit. They still accept anything within the limit at
  the end.
- Logs and the workflow history carry only ids and public offers.

## Repository layout

```
template.yaml               SAM: API, Lambdas, tables, KMS, state machine, alarms, budget
statemachine/negotiation.asl.json   one workflow per deal
src/
  interactions.py   Discord endpoint: signature check, commands, buttons, forms
  listing_agent.py  async jobs: photo -> listing, wants, publish, extra free times
  matcher.py        stream-triggered matching
  negotiator.py     one side's turn (deployed twice: seller and buyer) + final ask
  deals.py          start, schedule, confirm, finalize, reminders, handoff, reopen
  strategy.py       offer math and accept rule (pure)
  guard.py          output checks and injection wrapping (pure)
  scheduler.py      window overlap and meeting spot (pure)
  notify.py         Discord REST helpers
  store.py          DynamoDB, KMS, Secrets Manager helpers
  llm.py            Bedrock Converse wrapper
  categories.py     item categories
  data/places.json  curated public meeting spots (ASU Tempe; verify before launch)
layers/requirements.txt     third-party packages for the shared Lambda layer
scripts/
  build_layer.py        Linux wheels for the layer (no Docker needed)
  push_secrets.py       .env -> Secrets Manager
  register_commands.py  slash commands (test server, or --global)
  redteam.py            live prompt-injection check against Bedrock
tests/              unit, property and end-to-end tests (moto fakes AWS)
```

## Setup from scratch

### 1. Prerequisites

- Python 3.12+, the AWS SAM CLI, and the AWS CLI logged in to the target account.
- Bedrock access to an Anthropic model in us-east-2. Submit the Anthropic use-case form
  once per account (Bedrock console > Model catalog > the model). The default model is
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`; change `TextModelId` / `VisionModelId`
  in `template.yaml` to swap.

### 2. Discord application

1. <https://discord.com/developers/applications> > **New Application**.
2. **General Information**: copy the Application ID and Public Key.
3. **Bot**: **Reset Token**, copy it. No privileged intents are needed.
4. Create a server with a `#listings` channel and invite the bot:
   `https://discord.com/oauth2/authorize?client_id=<APP_ID>&scope=bot+applications.commands&permissions=274878024704`
5. Enable Developer Mode (User Settings > Advanced) and copy the server and channel ids.
6. Put everything in `.env` (git-ignored):

```
DISCORD_APP_ID=
DISCORD_PUBLIC_KEY=
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
DISCORD_LISTINGS_CHANNEL_ID=
```

### 3. Deploy

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python scripts\build_layer.py      # Linux wheels for the Lambda layer
sam build
sam deploy                                          # stack haggle-dev in us-east-2
.\.venv\Scripts\python scripts\push_secrets.py     # copies .env into Secrets Manager
.\.venv\Scripts\python scripts\register_commands.py
```

Paste the `InteractionsUrl` output into the developer portal under **Interactions
Endpoint URL** and save; Discord verifies it immediately. Confirm the AWS alert email.

`samconfig.toml` pins the region (the AWS organization only allows us-east-2) and the
alert email.

## Development

```powershell
.\.venv\Scripts\pytest            # all tests, no AWS needed
.\.venv\Scripts\ruff check .
```

Simulation mode: replay a negotiation with any limits, styles and reserves.

```powershell
.\.venv\Scripts\python src\strategy.py --asking 70 --floor 45 --ceiling 65
```

Live injection check (a few cents of Bedrock):

```powershell
$env:AWS_DEFAULT_REGION="us-east-2"
$env:TEXT_MODEL_ID="us.anthropic.claude-haiku-4-5-20251001-v1:0"
.\.venv\Scripts\python scripts\redteam.py
```

## Operations

- **Alarms** (email via SNS): errors in the interactions, listing agent and matcher
  functions; failed negotiation workflows.
- **Budget**: `haggle-dev-monthly`, alerts at $10 and $25 on resources tagged
  `project=haggle`. The tag must be activated as a cost allocation tag by the
  organization's management account before the budget sees spend.
- **A stuck deal**: open the execution in the Step Functions console
  (`haggle-dev-negotiation`); the deal id is in the execution name.
