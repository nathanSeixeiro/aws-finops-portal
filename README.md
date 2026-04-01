# CostWatch — AWS Cost Dashboard

Serverless dashboard that gives you real-time visibility into AWS spending across multiple accounts. Built with Python Lambdas, DynamoDB, API Gateway, and CDK.

![Dashboard](https://img.shields.io/badge/stack-serverless-green) ![Python](https://img.shields.io/badge/python-3.12-blue) ![CDK](https://img.shields.io/badge/aws--cdk-v2-orange)

## How It Works

```
EventBridge (cron) → Ingestion Lambda → Cost Explorer API → DynamoDB
                                                              ↓
                                                    Dashboard Snapshot
                                                              ↓
                     Frontend (browser) → API Gateway → Dashboard Lambda → DynamoDB (GetItem)
```

Cost data is fetched from AWS Cost Explorer on a schedule, converted to BRL, and stored in DynamoDB. A pre-computed dashboard snapshot is built after each ingestion so the frontend loads instantly with a single API call.

## Project Structure

```
src/
  handlers/
    ingest_costs.py          # Lambda: fetches costs from Cost Explorer, stores in DynamoDB
    get_dashboard.py         # Lambda: returns pre-computed dashboard snapshot (single GetItem)
  services/
    cost_ingestion_service.py    # Cost Explorer fetch + DynamoDB write logic
    dashboard_snapshot_service.py # Pre-computes all dashboard data into one DynamoDB item
    currency_service.py          # USD→BRL conversion via SSM Parameter Store
  repositories/
    cost_record_repository.py    # DynamoDB queries for cost records
  models/
    cost_record.py           # Pydantic v2 model for cost records
  utils/
    auth.py                  # API key validation
    aws_client.py            # boto3 client factory with dependency injection
    date_utils.py            # Date/period computation helpers
    response.py              # API Gateway response builder
cdk/
  app.py                     # CDK app entry point
  stacks/
    database_stack.py        # DynamoDB tables + GSIs
    api_stack.py             # API Gateway + Lambda functions
    scheduler_stack.py       # EventBridge cron rules
frontend/
  index.html                 # Dashboard UI
  app.js                     # Single /dashboard API call, renders everything client-side
  styles.css                 # Dark theme ("Command Center")
tests/                       # pytest + moto unit tests
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html) (`npm install -g aws-cdk`)
- AWS CLI configured with a named profile
- An AWS account with Cost Explorer enabled

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url> && cd costwatch
make install
```

### 2. Configure your AWS profile

The Makefile uses `--profile gsti-us` by default. To use your own profile, update the profile name in the `Makefile` (search and replace `gsti-us` with your profile name):

```bash
sed -i '' 's/gsti-us/your-profile/g' Makefile
```

### 3. Set the BRL exchange rate (optional)

```bash
aws ssm put-parameter \
  --name "/costwatch/brl-exchange-rate" \
  --value "5.34" \
  --type String \
  --profile your-profile
```

If not set, falls back to 5.05.

### 4. Bootstrap CDK (first time only)

```bash
make bootstrap
```

### 5. Deploy

```bash
make deploy
```

This runs: install → lint → test → synth → deploy. Three CloudFormation stacks are created:

| Stack | Resources |
|-------|-----------|
| CostWatchDatabaseStack | DynamoDB table (cost-records) + GSIs |
| CostWatchApiStack | API Gateway, 2 Lambdas (ingest + dashboard), IAM roles |
| CostWatchSchedulerStack | EventBridge rules (daily 2AM, weekly Mon 3AM, monthly 1st 4AM UTC) |

### 6. Seed historical data

After the first deploy, there's no data yet. Backfill it:

```bash
# Monthly data (last 12 months)
aws lambda invoke \
  --function-name <IngestCostsFunction-name> \
  --payload '{"detail":{"granularity":"MONTHLY","backfill_months":12}}' \
  --cli-binary-format raw-in-base64-out \
  --profile your-profile \
  /tmp/monthly.json

# Daily data (last 5 days per batch — repeat with higher numbers)
aws lambda invoke \
  --function-name <IngestCostsFunction-name> \
  --payload '{"detail":{"granularity":"DAILY","backfill_days":5}}' \
  --cli-binary-format raw-in-base64-out \
  --profile your-profile \
  /tmp/daily.json
```

Find the function name in the CDK deploy output or in the AWS Lambda console.

### 7. Update the frontend config

After deploy, update `frontend/app.js` with your API Gateway URL and API key:

```javascript
const CONFIG = {
  apiBase: "https://<your-api-id>.execute-api.<region>.amazonaws.com/prod",
  apiKey: "<your-api-key>",
};
```

The API URL is in the CDK deploy output. The API key value is set in `cdk/stacks/api_stack.py`.

### 8. Open the frontend

Serve `frontend/` locally with any static server:

```bash
# Using Python
python3 -m http.server 5500 -d frontend

# Or VS Code Live Server on port 5500
```

## Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make lint` | Run ruff linter |
| `make format` | Auto-format code with ruff |
| `make unit-testing` | Run pytest with coverage |
| `make synth` | Synthesize CloudFormation templates |
| `make diff` | Preview infrastructure changes |
| `make deploy` | Full pipeline: install → lint → test → synth → deploy |
| `make destroy` | Tear down all stacks and resources from AWS |
| `make bootstrap` | Bootstrap CDK in your AWS account (first time only) |

## Architecture Details

### Data Flow

1. **EventBridge** triggers the Ingestion Lambda on schedule (daily/weekly/monthly)
2. **Ingestion Lambda** calls AWS Cost Explorer API, converts USD→BRL, writes records to DynamoDB
3. After ingestion, it **pre-computes a dashboard snapshot** (KPIs, trends, service breakdown, account breakdown, heatmap) and stores it as a single DynamoDB item
4. **Dashboard Lambda** reads that one item on request — no computation, just a GetItem
5. **Frontend** makes one `GET /dashboard` call and renders everything client-side

### DynamoDB Schema

**Table: costwatch-cost-records**
- PK: `ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}`
- SK: `SERVICE#{service_name}`
- GSI `gsi-gran-period`: granularity (PK) + period (SK) — used for range queries
- GSI `gsi-service-period`: service_name (PK) + period (SK)
- GSI `gsi-account-gran`: account_id (PK) + account_gran_sk (SK)
- Dashboard snapshot stored as: PK=`SNAPSHOT#DASHBOARD`, SK=`LATEST`

### API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Returns the full pre-computed dashboard snapshot |

Requires `x-api-key` header.

## Customization

### Change AWS Profile

Update `gsti-us` in the `Makefile` to your AWS CLI profile name.

### Change Exchange Rate

```bash
aws ssm put-parameter --name "/costwatch/brl-exchange-rate" --value "5.50" --type String --overwrite --profile your-profile
```

Then re-ingest to apply the new rate to all records.

### Change API Key

Update the `api_key_value` in `cdk/stacks/api_stack.py` and redeploy. Then update `frontend/app.js` to match.

### Add CORS Origins

Update the `allow_origins` list in `cdk/stacks/api_stack.py` if serving the frontend from a different origin.
