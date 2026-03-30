# Kiro Spec Prompt — AWS Cost Dashboard (`project-costwatch`)

---

## Goal

Build a serverless AWS Cost Dashboard that gives a manager real-time and historical visibility into AWS spending across accounts, services, and teams. The system uses Python Lambdas, DynamoDB, CDK (Python), and exposes a read-only REST API consumed by a slick frontend dashboard. All infrastructure is deployed via CDK using the `gsti-us` AWS profile.

Cost data is fetched via the **AWS Cost Explorer MCP Server** (`awslabs.cost-explorer-mcp-server`) and stored in DynamoDB with dual-currency support (USD + BRL) and three granularities (DAILY, WEEKLY, MONTHLY).

---

## MCP Server Integration

The project uses the AWS Cost Explorer MCP server to fetch cost data. Configure it in `.kiro/mcp.json`:

```json
{
  "mcpServers": {
    "awslabs.cost-explorer-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.cost-explorer-mcp-server@latest"],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_PROFILE": "gsti-us"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

The ingestion Lambda calls Cost Explorer to fetch costs in **USD**. BRL amounts are computed at ingestion time using a live exchange rate fetched from an open exchange rate API (or a configurable static fallback rate stored in SSM Parameter Store as `/costwatch/brl-exchange-rate`). Both `amount_usd` and `amount_brl` are stored in DynamoDB. All API responses return both currencies. The frontend lets the manager toggle between USD and BRL.

---

## Architecture Overview (SDD)

### System Context

```
AWS Cost Explorer MCP Server (awslabs.cost-explorer-mcp-server)
        |
        v
[ Ingestion Lambda ]  --EventBridge (daily/weekly/monthly)-->  DynamoDB (3 tables)
        |
        v
[ API Lambdas ]  <---- API Gateway (REST) <---- Frontend Dashboard (S3 + CloudFront)
        |
        v
[ Alert Lambda ]  --> SNS Topic --> Email / Slack webhook
```

### Layers

| Layer | Responsibility |
|---|---|
| `handlers/` | Lambda entry points — thin, no business logic |
| `services/` | Orchestration, aggregation, business rules, currency conversion |
| `repositories/` | DynamoDB read/write access |
| `models/` | Pydantic v2 data models |
| `utils/` | Auth (API key), response builders, date helpers, currency converter |

---

## Project Structure

```
project-costwatch/
├── src/
│   ├── handlers/
│   │   ├── ingest_costs.py          # Triggered by EventBridge (all granularities)
│   │   ├── get_summary.py           # GET /summary
│   │   ├── get_service_breakdown.py # GET /services
│   │   ├── get_trend.py             # GET /trend
│   │   ├── get_anomalies.py         # GET /anomalies
│   │   ├── get_forecast.py          # GET /forecast
│   │   └── alert_check.py           # Triggered by EventBridge, sends SNS alerts
│   ├── services/
│   │   ├── cost_ingestion_service.py
│   │   ├── cost_query_service.py
│   │   ├── anomaly_detection_service.py
│   │   ├── forecast_service.py
│   │   └── currency_service.py      # USD->BRL conversion, rate caching from SSM
│   ├── repositories/
│   │   ├── cost_record_repository.py
│   │   ├── alert_config_repository.py
│   │   └── budget_repository.py
│   ├── models/
│   │   ├── cost_record.py
│   │   ├── service_breakdown.py
│   │   ├── alert_config.py
│   │   └── budget.py
│   └── utils/
│       ├── response.py              # Standard API response builder
│       ├── auth.py                  # API key validation via header
│       ├── date_utils.py            # ISO date helpers, week/month period logic
│       └── aws_client.py            # Boto3 client factory (Cost Explorer, SNS, SSM)
├── cdk/
│   ├── app.py
│   ├── cdk.json
│   └── stacks/
│       ├── database_stack.py        # DynamoDB tables + GSIs
│       ├── api_stack.py             # API Gateway + Lambda functions + IAM
│       ├── scheduler_stack.py       # EventBridge rules (daily, weekly, monthly)
│       ├── alert_stack.py           # SNS topic + alert Lambda
│       └── frontend_stack.py        # S3 bucket + CloudFront distribution
├── tests/
│   ├── handlers/
│   │   ├── test_ingest_costs.py
│   │   ├── test_get_summary.py
│   │   ├── test_get_service_breakdown.py
│   │   ├── test_get_trend.py
│   │   ├── test_get_anomalies.py
│   │   └── test_get_forecast.py
│   ├── services/
│   │   ├── test_cost_ingestion_service.py
│   │   ├── test_cost_query_service.py
│   │   ├── test_anomaly_detection_service.py
│   │   ├── test_forecast_service.py
│   │   └── test_currency_service.py
│   ├── repositories/
│   │   ├── test_cost_record_repository.py
│   │   └── test_budget_repository.py
│   └── utils/
│       ├── test_response.py
│       ├── test_auth.py
│       └── test_date_utils.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── .kiro/
│   └── mcp.json                     # MCP server config (see above)
├── docs/
│   └── HLD.md
├── scripts/
│   └── bootstrap.sh
├── Makefile
├── pyproject.toml
├── .python-version
└── .mise.toml
```

---

## DynamoDB Tables — Exact Specification

### Table 1: `costwatch-cost-records`

**Purpose:** Stores cost data per AWS service per account, for all three granularities, in both USD and BRL.

| Attribute | Type | Description |
|---|---|---|
| `pk` | String (PK) | `ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}` |
| `sk` | String (SK) | `SERVICE#{service_name}` |
| `account_id` | String | AWS account ID (12 digits) |
| `account_alias` | String | Human-readable alias (e.g. `production`) |
| `period` | String | Period start: `YYYY-MM-DD` for DAILY/WEEKLY, `YYYY-MM` for MONTHLY |
| `period_end` | String | Period end date (inclusive) |
| `granularity` | String | `DAILY`, `WEEKLY`, or `MONTHLY` |
| `service_name` | String | AWS service name (e.g. `Amazon EC2`) |
| `amount_usd` | Number | Cost in USD (4 decimal places) |
| `amount_brl` | Number | Cost in BRL (4 decimal places) |
| `exchange_rate` | Number | USD->BRL rate used at ingestion time |
| `tags` | Map | Cost allocation tags (e.g. `{"team": "platform", "env": "prod"}`) |
| `ingested_at` | String | ISO 8601 timestamp of ingestion |
| `ttl` | Number | Unix epoch — DAILY: 365d, WEEKLY: 2y, MONTHLY: 5y |

**PK examples by granularity:**
- Daily:   `ACCOUNT#123456789012#GRAN#DAILY#PERIOD#2024-03-15`
- Weekly:  `ACCOUNT#123456789012#GRAN#WEEKLY#PERIOD#2024-03-11`
- Monthly: `ACCOUNT#123456789012#GRAN#MONTHLY#PERIOD#2024-03`

**GSI 1:** `gsi-gran-period`
- PK: `granularity` (String)
- SK: `period` (String)
- Use case: Query all accounts/services for a given granularity + period

**GSI 2:** `gsi-service-period`
- PK: `service_name` (String)
- SK: `period` (String)
- Use case: Trend chart for a single service across time periods

**GSI 3:** `gsi-account-gran`
- PK: `account_id` (String)
- SK: composite `granularity#period` (e.g. `DAILY#2024-03-15`)
- Use case: All costs for a single account, filterable by granularity + date range

**Billing mode:** PAY_PER_REQUEST
**Point-in-time recovery:** Enabled
**Encryption:** AWS_OWNED_KEY

---

### Table 2: `costwatch-budgets`

**Purpose:** Monthly budget thresholds per account or team, in both currencies.

| Attribute | Type | Description |
|---|---|---|
| `pk` | String (PK) | `ACCOUNT#{account_id}` or `TEAM#{team_name}` |
| `sk` | String (SK) | `BUDGET#MONTHLY` |
| `budget_usd` | Number | Monthly budget limit in USD |
| `budget_brl` | Number | Monthly budget limit in BRL (computed from USD at creation time) |
| `alert_threshold_pct` | Number | Alert when spend reaches this % (e.g. 80) |
| `owner_email` | String | Email for alerts |
| `created_at` | String | ISO 8601 creation timestamp |
| `updated_at` | String | ISO 8601 last update timestamp |

**Billing mode:** PAY_PER_REQUEST
**Encryption:** AWS_OWNED_KEY

---

### Table 3: `costwatch-alert-configs`

**Purpose:** Anomaly detection config and alert history.

| Attribute | Type | Description |
|---|---|---|
| `pk` | String (PK) | `ACCOUNT#{account_id}` |
| `sk` | String (SK) | `ALERT#{YYYY-MM-DD}#{service_name}` |
| `alert_type` | String | `ANOMALY` or `BUDGET_BREACH` |
| `granularity` | String | Granularity that triggered the alert |
| `service_name` | String | Affected AWS service |
| `expected_amount_usd` | Number | Baseline expected cost in USD |
| `actual_amount_usd` | Number | Actual cost in USD |
| `expected_amount_brl` | Number | Baseline expected cost in BRL |
| `actual_amount_brl` | Number | Actual cost in BRL |
| `deviation_pct` | Number | Percentage deviation from baseline |
| `status` | String | `SENT`, `SUPPRESSED`, or `PENDING` |
| `sent_at` | String | ISO 8601 timestamp when alert was sent |
| `ttl` | Number | Unix epoch — expires after 90 days |

**Billing mode:** PAY_PER_REQUEST
**Encryption:** AWS_OWNED_KEY

---

## Granularity Logic

Each granularity has its own EventBridge schedule. The Lambda receives the granularity in the event detail.

| Granularity | Schedule | Period fetched |
|---|---|---|
| `DAILY` | Every day at 02:00 UTC | Yesterday (`YYYY-MM-DD`) |
| `WEEKLY` | Every Monday at 03:00 UTC | Previous ISO week Mon–Sun |
| `MONTHLY` | 1st of every month at 04:00 UTC | Previous full month (`YYYY-MM`) |

EventBridge event detail: `{ "granularity": "DAILY" | "WEEKLY" | "MONTHLY" }`

The ingestion service sets the `period` key format and TTL value based on granularity.

---

## Currency Service

`src/services/currency_service.py`:
- Fetches the USD->BRL exchange rate from SSM Parameter Store: `/costwatch/brl-exchange-rate`
- Multiplies `amount_usd` by the rate to produce `amount_brl`
- Stores both values and `exchange_rate` used in DynamoDB
- The SSM parameter is updated manually or via a separate scheduled Lambda
- Unit-tested with mocked SSM responses

All API responses include both `amount_usd` and `amount_brl`. The frontend sends `?currency=USD|BRL` for display preference.

---

## API Endpoints

| Method | Path | Lambda | Query Params |
|---|---|---|---|
| GET | `/summary` | `get_summary` | `?currency=USD\|BRL` |
| GET | `/services` | `get_service_breakdown` | `?granularity=DAILY\|WEEKLY\|MONTHLY&period=…&currency=…` |
| GET | `/trend` | `get_trend` | `?granularity=DAILY\|WEEKLY\|MONTHLY&n=30&currency=…` |
| GET | `/anomalies` | `get_anomalies` | `?currency=…` |
| GET | `/forecast` | `get_forecast` | `?currency=…` |

All endpoints require `x-api-key` header. API Gateway enforces API key + usage plan (100 req/min, burst 50).

---

## Frontend UI — "Dark Command Center"

**CRITICAL: This must be a stunning, award-worthy dashboard. Not a generic admin panel.**

### Aesthetic

Think mission control meets fintech. Bloomberg Terminal evolved. Deep near-black backgrounds with razor-sharp neon green for positive numbers and vivid coral for anomalies. Dense with information but absolutely intentional — every pixel has a purpose.

**Typography:**
- Display/headings: `Space Mono` (Google Fonts) — monospaced, technical, authoritative
- Body/labels: `DM Sans` — clean contrast to the mono display font
- All cost numbers in `Space Mono` with tabular figures

**CSS Variables:**
```css
--bg-deep: #0A0E14;
--bg-surface: #111820;
--bg-card: #161D27;
--bg-card-hover: #1C2535;
--accent-green: #00FF87;
--accent-coral: #FF4757;
--accent-amber: #FFB830;
--accent-blue: #3D9DF3;
--text-primary: #E8EDF5;
--text-secondary: #7A8BA0;
--text-muted: #3D4F63;
--border: #1E2C3D;
--border-glow: rgba(0, 255, 135, 0.15);
```

### Layout

```
+-------------------------------------------------------------------+
|  HEADER: CostWatch logo · [USD | BRL] pill toggle · last synced   |
+------------+------------+------------+---------------------------+
|  KPI: Today |  KPI: MTD  | KPI: Prev  |  KPI: Forecast           |
+------------+------------+------------+---------------------------+
|  TREND CHART — full width, tabs: [Daily] [Weekly] [Monthly]       |
+-----------------------------------+-------------------------------+
|  TOP 10 SERVICES (horiz. bars)    |  ACCOUNT BREAKDOWN (donut)   |
+-----------------------------------+-------------------------------+
|  SERVICE HEATMAP (services x periods, intensity = cost)           |
+-----------------------------------+-------------------------------+
|  BUDGET TRACKER (progress bars)   |  ANOMALY FEED (alert list)   |
+-----------------------------------+-------------------------------+
|  TEAM COST TABLE (sortable, searchable)                           |
+-------------------------------------------------------------------+
```

### Widget Specifications

**KPI Cards (x4)**
- Large animated number (Space Mono) counting up from 0 on page load (1.2s easeOutExpo)
- Currency symbol ($ or R$) inline, smaller size
- Tiny inline sparkline SVG — 60px wide x 24px tall — last 7 periods
- Delta badge: "+12.4% vs last month" colored green (improvement) or coral (overspend)
- Top border: 2px solid `--accent-green`
- On hover: subtle green glow `box-shadow: 0 0 20px var(--border-glow)` + lift `translateY(-2px)`

**Trend Chart**
- Chart.js line chart, full dark theme
- Smooth curves (tension: 0.4), gradient fill under line (accent-green 20% -> transparent)
- Three tabs above: Daily / Weekly / Monthly — switching re-fetches with 600ms animated transition
- Custom tooltip: dark card showing exact amount in both USD and BRL
- Y-axis amounts formatted with K/M suffixes

**Top Services Bar Chart**
- Horizontal bars, sorted descending by amount
- Bar fill: gradient left-to-right from accent-blue to accent-green
- Service name on left, formatted amount on right in Space Mono
- Hover: bar brightens, tooltip shows % of total spend
- "Show all" toggle to expand beyond top 10

**Account Breakdown Donut**
- Chart.js doughnut with custom dark palette
- Center label: total amount (animated counter) + "Total" label
- Legend: account alias + amount + % share
- Hover: slice explodes slightly outward

**Service Heatmap**
- CSS grid: rows = top 10 services, columns = last 8 periods
- Cell color: --bg-card (near zero) -> accent-amber (medium) -> accent-coral (high)
- Tooltip on hover: exact amount + period label
- Period labels across top, service names down left
- Color scale legend bar at the bottom

**Budget Tracker**
- One row per account/team: name, animated progress bar, "R$ X of R$ Y"
- Bar color: accent-green (< 70%) -> accent-amber (70-90%) -> accent-coral (> 90%)
- "OVER BUDGET" pill badge in coral if > 100%
- Bar fills animate on load

**Anomaly Feed**
- Cards sorted by most recent, pulsing coral dot for unacknowledged
- Each card: service abbreviation badge, service name, actual vs expected, deviation %, date
- Severity pills: CRITICAL (coral) / WARNING (amber) / INFO (blue)

**Team Cost Table**
- Columns: Team, Daily Avg, Weekly Total, Monthly Total, % of Total, Trend (sparkline)
- Click column header to sort ascending/descending
- Search input with live filtering
- Subtle zebra rows, hover highlight
- All amounts animate between currencies on toggle

### Animations and Interactions

- Page load: all cards fade in with staggered `animation-delay` (0ms, 80ms, 160ms…)
- All number counters animate 0 -> value over 1.2s (CSS + JS requestAnimationFrame)
- Currency toggle (USD/BRL pill in header): all amounts on the page animate to new values
- Chart transitions: 600ms easeInOutCubic
- Heatmap: cells fade in row by row on load
- Pulsing dot on anomaly cards: CSS keyframe pulse animation
- Live indicator in header: small pulsing green dot + "Live" text

### Technical Stack

Single `index.html` + `app.js` + `styles.css` — no framework, vanilla JS.
- Chart.js from CDN for trend line, donut, bar chart
- Google Fonts: Space Mono + DM Sans
- `fetch()` for API calls
- Top of `app.js`: `const CONFIG = { apiBase: "https://YOUR_API_GW_URL", apiKey: "YOUR_KEY" }`
- Deployed to S3 via CDK `BucketDeployment`, served through CloudFront

---

## Security Design

### IAM / Least Privilege
- Each Lambda has its own IAM role (no shared roles, no wildcards)
- **Ingestion Lambda:** `ce:GetCostAndUsage`, `ce:GetCostForecast`; DynamoDB `PutItem`/`UpdateItem` on cost-records; SSM `GetParameter` for `/costwatch/brl-exchange-rate`
- **Query Lambdas:** DynamoDB `GetItem`, `Query` (read-only) on their tables only
- **Alert Lambda:** SNS `Publish` on specific topic ARN; DynamoDB read on cost-records + write on alert-configs

### API Security
- API Gateway: API Key + Usage Plan (100 req/min, burst 50)
- API key stored in AWS Secrets Manager, never hardcoded or logged
- HTTPS only (TLS 1.2+)
- `x-api-key` validated in `utils/auth.py` before any business logic
- CORS: allowed origin = CloudFront distribution URL only

### Data Security
- DynamoDB: encryption at rest (AWS_OWNED_KEY), PITR enabled
- Lambda secrets: SSM Parameter Store (SecureString)
- S3: versioning on, public access blocked, SSE-S3 encryption
- CloudFront: OAI enforced — S3 bucket never publicly accessible
- SNS: KMS encrypted
- CloudWatch Logs: 30-day retention on all Lambda log groups

### Network
- Lambdas optionally in VPC (configurable via CDK context key `use_vpc`)
- VPC endpoints for DynamoDB and SSM to avoid public internet traffic

---

## CDK Stacks

### `DatabaseStack`
- All 3 DynamoDB tables with GSIs, TTL, PITR as specified
- Exports table names + ARNs as CloudFormation outputs

### `ApiStack`
- API Gateway REST API with API key + usage plan
- One Lambda per handler, each with its own IAM role
- Lambda env vars: table names, SNS topic ARN, SSM paths

### `SchedulerStack`
- EventBridge rule: daily 02:00 UTC -> `ingest_costs` `{"granularity": "DAILY"}`
- EventBridge rule: Monday 03:00 UTC -> `ingest_costs` `{"granularity": "WEEKLY"}`
- EventBridge rule: 1st of month 04:00 UTC -> `ingest_costs` `{"granularity": "MONTHLY"}`
- EventBridge rule: daily 07:00 UTC -> `alert_check`

### `AlertStack`
- KMS-encrypted SNS topic
- Alert Lambda with SNS publish permission

### `FrontendStack`
- Private S3 bucket (versioned, SSE-S3, public access blocked)
- CloudFront distribution with OAI
- `BucketDeployment` to deploy `frontend/` directory
- Output: CloudFront URL

---

## Makefile

```makefile
.PHONY: deploy unit-testing lint format install bootstrap synth diff

PROFILE = gsti-us
CDK_DIR = cdk

install:
	uv sync

bootstrap:
	cd $(CDK_DIR) && cdk bootstrap --profile $(PROFILE)

deploy:
	cd $(CDK_DIR) && cdk deploy --all --profile $(PROFILE) --require-approval never

unit-testing:
	uv run pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

synth:
	cd $(CDK_DIR) && cdk synth --profile $(PROFILE)

diff:
	cd $(CDK_DIR) && cdk diff --profile $(PROFILE)
```

---

## Unit Testing

- pytest + moto (DynamoDB, SNS, SSM) — no real AWS calls
- Dependency injection on all AWS clients
- >80% coverage target across `src/`

| Test | What it covers |
|---|---|
| `test_ingest_costs.py` | DAILY/WEEKLY/MONTHLY event parsing, period key format, DynamoDB write |
| `test_cost_query_service.py` | Aggregation, granularity filter, MoM calculation |
| `test_currency_service.py` | SSM rate fetch, BRL conversion, fallback behavior |
| `test_anomaly_detection_service.py` | Std deviation, threshold logic, alert creation |
| `test_auth.py` | Missing key 401, invalid key 401, valid key passes |
| `test_response.py` | Response envelope, both currencies present in payload |

---

## pyproject.toml

```toml
[project]
name = "project-costwatch"
requires-python = ">=3.12"

[project.dependencies]
pydantic = ">=2.0"
boto3 = ">=1.34"
aws-cdk-lib = ">=2.140"
constructs = ">=10.0"
requests = ">=2.31"

[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "moto[dynamodb,sns,ssm]",
  "ruff",
]
```

---

## .mise.toml

```toml
[tools]
python = "3.12"
node = "20"
"npm:aws-cdk" = "latest"

[env]
AWS_PROFILE = "gsti-us"
```

---

## Kiro Planning Instructions

Implement this project in the following order:

1. **Scaffold** all directories and empty files; create `.kiro/mcp.json` with the MCP config shown above
2. **DynamoDB tables** in `database_stack.py` — use exact PK/SK patterns, all 3 GSIs on cost-records, TTL (granularity-aware), PITR
3. **Pydantic models** — every model with `amount_usd: Decimal`, `amount_brl: Decimal`, `granularity: Literal["DAILY","WEEKLY","MONTHLY"]`
4. **`currency_service.py`** — SSM rate fetch, USD->BRL multiply, store both + `exchange_rate` field
5. **Repositories** — use exact key patterns from the table spec above for every boto3 call
6. **Services** — ingestion handles all 3 granularities from EventBridge detail; query service accepts `granularity` param; anomaly service uses 30-period rolling baseline
7. **Lambda handlers** — thin wrappers; every response payload includes both `amount_usd` and `amount_brl`
8. **CDK stacks** — all 5 stacks; SchedulerStack must have all 3 EventBridge rules with correct cron expressions
9. **Makefile** — `deploy` uses `gsti-us`; `unit-testing` runs pytest with coverage report
10. **Unit tests** — every handler, service, repository, utility
11. **Frontend** — implement the full "Dark Command Center" design: Space Mono + DM Sans, CSS variables palette, animated KPI cards with sparklines, Chart.js trend/donut/bar, heatmap grid, animated budget tracker, anomaly feed, team table, USD<->BRL animated toggle
12. **Security hardening** — per-Lambda IAM roles, Secrets Manager for API key, SSM SecureString for BRL rate, no `*` anywhere, CloudFront OAI
