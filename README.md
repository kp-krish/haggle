# Haggle

Agents that bargain for you. Every student gets a personal agent in Discord that lists,
finds, bargains and schedules pickups, while each student's price limit stays secret from
the other side.

- **Code picks every number; the model only writes the words.**
- Serverless on AWS (us-east-2): API Gateway, Lambda (Python 3.12), Step Functions,
  DynamoDB + KMS, S3, Bedrock, EventBridge Scheduler.

See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) for build phases and
`Haggle-Architecture.pdf` for the full design.

## Layout

```
src/
  strategy.py    offer math and accept rule (pure, no AWS)
  guard.py       output checks and prompt-injection wrapping (pure)
  scheduler.py   pickup window overlap and meeting spot (pure)
data/places.json curated public meeting spots
tests/           unit and property tests
```

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\pytest
```

## Deploy

```powershell
.\.venv\Scripts\python scripts\build_layer.py   # Linux wheels for the Lambda layer
sam build
sam deploy                                       # stack haggle-dev in us-east-2
.\.venv\Scripts\python scripts\push_secrets.py  # copies .env into Secrets Manager
```

Paste the `InteractionsUrl` output into the Discord developer portal under
**Interactions Endpoint URL**.

### Simulation mode

`strategy.py` and `scheduler.py` run without AWS or Discord:

```powershell
.\.venv\Scripts\python src\strategy.py --asking 70 --floor 45 --ceiling 65
```
