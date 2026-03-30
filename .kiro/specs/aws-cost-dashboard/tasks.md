# Implementation Plan: CostWatch AWS Cost Dashboard

## Overview

Incremental implementation of the CostWatch serverless AWS Cost Dashboard. Tasks build on each other starting with project scaffolding and tooling, then data models, repository layer, service layer, Lambda handlers, CDK infrastructure, and finally the frontend dashboard. Each task references specific requirements for traceability.

## Tasks

- [x] 1. Project scaffolding and tooling setup
  - [x] 1.1 Create project directory structure and configuration files
    - Create `pyproject.toml` with `uv` as package manager, declaring dependencies: pydantic (>=2.0), boto3 (>=1.34), aws-cdk-lib (>=2.140), constructs (>=10.0), requests (>=2.31), and dev dependencies: pytest, moto, pytest-cov, ruff
    - Create `.mise.toml` configuring Python 3.12, Node 20, aws-cdk (latest), with `AWS_PROFILE=gsti-us`
    - Create `.python-version` with `3.12`
    - Create `Makefile` with targets: `deploy`, `unit-testing`, `lint`, `format`, `install`, `bootstrap`, `synth`, `diff`
    - Create empty `__init__.py` files for all Python packages: `src/`, `src/handlers/`, `src/services/`, `src/repositories/`, `src/models/`, `src/utils/`, `tests/`, `tests/handlers/`, `tests/services/`, `tests/repositories/`, `tests/utils/`
    - _Requirements: 17.1, 17.2, 17.3_

  - [x] 1.2 Create MCP server configuration
    - Create `.kiro/mcp.json` configuring `awslabs.cost-explorer-mcp-server` with `uvx` command, `AWS_PROFILE=gsti-us`, `FASTMCP_LOG_LEVEL=ERROR`
    - _Requirements: 18.1_

- [x] 2. Pydantic data models
  - [x] 2.1 Implement CostRecord model
    - Create `src/models/cost_record.py` with `CostRecord` Pydantic v2 model
    - Fields: `pk`, `sk`, `account_id`, `account_alias`, `period`, `period_end`, `granularity` (Literal["DAILY","WEEKLY","MONTHLY"]), `service_name`, `amount_usd` (Decimal, 4 places), `amount_brl` (Decimal, 4 places), `exchange_rate` (Decimal), `tags` (dict), `ingested_at` (str), `ttl` (int)
    - Add `to_dynamodb_item()` and `from_dynamodb_item()` helper methods
    - _Requirements: 13.1_

  - [x] 2.2 Implement Budget model
    - Create `src/models/budget.py` with `Budget` Pydantic v2 model
    - Fields: `pk`, `sk`, `budget_usd` (Decimal), `budget_brl` (Decimal), `alert_threshold_pct` (Decimal), `owner_email`, `created_at`, `updated_at`
    - Add `to_dynamodb_item()` and `from_dynamodb_item()` helper methods
    - _Requirements: 13.3_

  - [x] 2.3 Implement ServiceBreakdown model
    - Create `src/models/service_breakdown.py` with `ServiceBreakdown` Pydantic v2 model
    - Fields: `service_name`, `amount_usd` (Decimal), `amount_brl` (Decimal), `percentage_of_total` (Decimal)
    - _Requirements: 13.2_

  - [x] 2.4 Write unit tests for Pydantic models
    - Test CostRecord validation, serialization, and DynamoDB round-trip
    - Test Budget validation and serialization
    - Test ServiceBreakdown percentage computation
    - _Requirements: 13.1, 13.2, 13.3_

- [x] 3. Utility modules
  - [x] 3.1 Implement aws_client.py
    - Create `src/utils/aws_client.py` with factory functions: `get_dynamodb_resource()`, `get_ssm_client()`, `get_ce_client()`
    - Support dependency injection by accepting optional client/resource parameters
    - _Requirements: 14.4, 16.7_

  - [x] 3.2 Implement response.py
    - Create `src/utils/response.py` with `success(body, status_code=200)` and `error(message, status_code)` functions
    - Include CORS headers (`Access-Control-Allow-Origin: *`), `Content-Type: application/json`
    - Use `json.dumps` with `default=str` for Decimal serialization
    - _Requirements: 4.6, 2.5_

  - [x] 3.3 Implement auth.py
    - Create `src/utils/auth.py` with `validate_api_key(event)` function
    - Read expected API key from `API_KEY` environment variable
    - Extract `x-api-key` from event headers (case-insensitive)
    - Return True/False for valid/invalid key
    - _Requirements: 4.5, 12.2_

  - [x] 3.4 Implement date_utils.py
    - Create `src/utils/date_utils.py` with functions: `get_yesterday()`, `get_previous_week()`, `get_previous_month()`, `get_current_month()`, `get_last_n_periods(granularity, n)`
    - `get_yesterday()` returns `YYYY-MM-DD`
    - `get_previous_week()` returns `(week_start, week_end)` as `YYYY-MM-DD` (ISO Monday-Sunday)
    - `get_previous_month()` returns `YYYY-MM`
    - `get_last_n_periods()` returns list of period strings for the given granularity
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 3.5 Write unit tests for utility modules
    - Test `auth.py`: missing API key → False, invalid key → False, valid key → True
    - Test `response.py`: success envelope includes correct headers and body; error envelope includes error message; both handle Decimal values
    - Test `date_utils.py`: verify period formats, edge cases (month boundaries, year boundaries, ISO week computation)
    - _Requirements: 16.4, 16.5_

- [x] 4. Checkpoint — Verify models and utilities
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Repository layer
  - [x] 5.1 Implement cost_record_repository.py
    - Create `src/repositories/cost_record_repository.py` with `CostRecordRepository` class
    - Constructor accepts a DynamoDB table resource (dependency injection)
    - `put(record: CostRecord)` — PutItem with pk=`ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}`, sk=`SERVICE#{service_name}`
    - `query_by_gran_period(granularity, period)` — Query GSI `gsi-gran-period`
    - `query_by_service_period(service, period_start, period_end)` — Query GSI `gsi-service-period` with SK range
    - `query_by_account_gran(account_id, granularity, period_start, period_end)` — Query GSI `gsi-account-gran` with composite SK range (`granularity#period`)
    - _Requirements: 14.1, 14.3, 14.4_

  - [x] 5.2 Implement budget_repository.py
    - Create `src/repositories/budget_repository.py` with `BudgetRepository` class
    - Constructor accepts a DynamoDB table resource (dependency injection)
    - `get_account_budget(account_id)` — GetItem with pk=`ACCOUNT#{account_id}`, sk=`BUDGET#MONTHLY`
    - `get_team_budget(team_name)` — GetItem with pk=`TEAM#{team_name}`, sk=`BUDGET#MONTHLY`
    - `list_all_budgets()` — Scan (small table, scan is acceptable)
    - _Requirements: 14.2, 14.4_

  - [ ]* 5.3 Write unit tests for repositories
    - Use moto to mock DynamoDB tables with correct schemas and GSIs
    - Test `CostRecordRepository`: put and query by each GSI, verify key patterns
    - Test `BudgetRepository`: get_account_budget, get_team_budget, list_all_budgets
    - Test empty result sets and multiple records
    - _Requirements: 16.1, 16.3_

- [-] 6. Service layer
  - [x] 6.1 Implement currency_service.py
    - Create `src/services/currency_service.py` with `CurrencyService` class
    - Constructor accepts SSM client (dependency injection)
    - `FALLBACK_RATE = Decimal("5.05")`, `SSM_PATH = "/costwatch/brl-exchange-rate"`
    - `get_exchange_rate()` — Fetch from SSM, cache for Lambda invocation lifetime; on failure, use fallback rate and log warning
    - `convert(amount_usd, rate)` — Multiply and round to 4 decimal places using `ROUND_HALF_UP`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 15.4_

  - [ ]* 6.2 Write unit tests for currency_service.py
    - Use moto to mock SSM Parameter Store
    - Test SSM rate fetch returns correct Decimal value
    - Test BRL conversion accuracy (4 decimal places, ROUND_HALF_UP)
    - Test fallback behavior when SSM is unavailable or parameter missing
    - Test caching: second call does not hit SSM again
    - _Requirements: 16.6_

  - [x] 6.3 Implement cost_ingestion_service.py
    - Create `src/services/cost_ingestion_service.py` with `CostIngestionService` class
    - Constructor accepts `CostRecordRepository` and `CurrencyService`
    - `ingest(granularity)` — Compute period, fetch exchange rate, fetch costs from Cost Explorer, convert to BRL, set TTL, store each record
    - `_compute_period(granularity)` — Return (period_start, period_end) using date_utils
    - `_compute_ttl(granularity)` — DAILY=365d, WEEKLY=2y, MONTHLY=5y from now
    - `_fetch_costs(granularity, period)` — Call Cost Explorer `get_cost_and_usage` via boto3 CE client
    - Handle MCP/CE errors: log error with granularity and period context, exit without writing partial data
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 15.1_

  - [ ]* 6.4 Write unit tests for cost_ingestion_service.py
    - Mock CostRecordRepository and CurrencyService
    - Test DAILY ingestion: correct period format, TTL=365d, records stored
    - Test WEEKLY ingestion: correct ISO week period, TTL=2y
    - Test MONTHLY ingestion: correct YYYY-MM period, TTL=5y
    - Test error handling: CE failure logs error and writes no records
    - _Requirements: 16.3_

  - [x] 6.5 Implement cost_query_service.py
    - Create `src/services/cost_query_service.py` with `CostQueryService` class
    - Constructor accepts `CostRecordRepository` and `BudgetRepository`
    - `get_summary()` — Return today's cost, MTD total, previous month total, forecast amount in both currencies
    - `get_service_breakdown(granularity, period)` — Query by gran+period, aggregate by service, compute percentages, sort descending
    - `get_trend(granularity, n)` — Get last n periods, aggregate totals per period, return list of `{period, total_usd, total_brl}`
    - _Requirements: 4.1, 4.2, 4.3, 15.2_

  - [x] 6.6 Implement forecast_service.py
    - Create `src/services/forecast_service.py` with `ForecastService` class
    - Constructor accepts `CostRecordRepository`
    - `get_forecast()` — Calculate projected monthly cost based on daily spending rate (MTD spend / days elapsed * days in month)
    - Return `{forecast_usd, forecast_brl, method, confidence}`
    - _Requirements: 4.4, 15.3_

  - [ ]* 6.7 Write unit tests for cost_query_service.py and forecast_service.py
    - Mock repositories with sample data
    - Test get_summary returns all four metrics in both currencies
    - Test get_service_breakdown sorts descending and computes percentages
    - Test get_trend returns correct number of periods
    - Test get_forecast projection calculation
    - _Requirements: 16.3_

- [x] 7. Checkpoint — Verify service layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Lambda handlers
  - [x] 8.1 Implement ingest_costs.py handler
    - Create `src/handlers/ingest_costs.py`
    - Parse EventBridge event to extract `granularity` from event detail
    - Instantiate services with real AWS clients from `aws_client.py`
    - Delegate to `CostIngestionService.ingest(granularity)`
    - Return success/failure dict (not API-facing)
    - _Requirements: 1.1, 1.2, 1.3, 15.5_

  - [x] 8.2 Implement get_summary.py handler
    - Create `src/handlers/get_summary.py`
    - Validate API key via `auth.validate_api_key(event)`; return 401 if invalid
    - Delegate to `CostQueryService.get_summary()`
    - Return response via `response.success()` with both USD and BRL amounts
    - _Requirements: 4.1, 4.5, 4.6, 15.5_

  - [x] 8.3 Implement get_service_breakdown.py handler
    - Create `src/handlers/get_service_breakdown.py`
    - Validate API key; return 401 if invalid
    - Parse and validate query parameters: `granularity` (required), `period` (required), `currency` (optional)
    - Return 400 if required params missing
    - Delegate to `CostQueryService.get_service_breakdown(granularity, period)`
    - Return response via `response.success()`
    - _Requirements: 4.2, 4.5, 4.6, 15.5_

  - [x] 8.4 Implement get_trend.py handler
    - Create `src/handlers/get_trend.py`
    - Validate API key; return 401 if invalid
    - Parse query parameters: `granularity` (required), `n` (optional, default 30), `currency` (optional)
    - Return 400 if required params missing
    - Delegate to `CostQueryService.get_trend(granularity, n)`
    - Return response via `response.success()`
    - _Requirements: 4.3, 4.5, 4.6, 15.5_

  - [x] 8.5 Implement get_forecast.py handler
    - Create `src/handlers/get_forecast.py`
    - Validate API key; return 401 if invalid
    - Delegate to `ForecastService.get_forecast()`
    - Return response via `response.success()`
    - _Requirements: 4.4, 4.5, 4.6, 15.5_

  - [ ]* 8.6 Write unit tests for all Lambda handlers
    - Test each handler with valid API key → 200 response with correct body structure
    - Test each API handler with missing/invalid API key → 401 response
    - Test get_service_breakdown and get_trend with missing required params → 400 response
    - Test ingest_costs handler with valid EventBridge event
    - Mock service layer calls; verify handlers are thin wrappers with no business logic
    - _Requirements: 16.3, 16.4_

- [x] 9. Checkpoint — Verify handlers and full backend
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. CDK infrastructure — DatabaseStack
  - [x] 10.1 Implement database_stack.py
    - Create `cdk/stacks/database_stack.py` with `DatabaseStack` class
    - Create `costwatch-cost-records` table: pk=`pk` (String), sk=`sk` (String), PAY_PER_REQUEST billing
    - Add GSI `gsi-gran-period`: pk=`granularity`, sk=`period`
    - Add GSI `gsi-service-period`: pk=`service_name`, sk=`period`
    - Add GSI `gsi-account-gran`: pk=`account_id`, sk=composite `granularity#period`
    - Enable TTL on attribute `ttl`
    - Enable point-in-time recovery
    - Enable encryption at rest (AWS_OWNED_KEY)
    - Create `costwatch-budgets` table: pk=`pk` (String), sk=`sk` (String), PAY_PER_REQUEST billing
    - Enable encryption at rest on budgets table (AWS_OWNED_KEY)
    - Export table names and ARNs as CloudFormation outputs
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 12.4, 12.5_

- [x] 11. CDK infrastructure — ApiStack
  - [x] 11.1 Implement api_stack.py
    - Create `cdk/stacks/api_stack.py` with `ApiStack` class
    - Accept DatabaseStack outputs (table names, ARNs) as constructor parameters
    - Create 5 Lambda functions (Python 3.12 runtime): `ingest_costs`, `get_summary`, `get_service_breakdown`, `get_trend`, `get_forecast`
    - Set Lambda handler entry points to `src/handlers/<name>.handler`
    - Pass DynamoDB table names and SSM parameter path as environment variables to each Lambda
    - Create per-Lambda IAM roles:
      - Query Lambdas: read-only DynamoDB (`GetItem`, `Query`) scoped to specific table ARNs and GSI ARNs
      - Ingestion Lambda: `ce:GetCostAndUsage`, `ce:GetCostForecast`, DynamoDB `PutItem`/`UpdateItem` on cost-records table, SSM `GetParameter` for `/costwatch/brl-exchange-rate`
    - No wildcard (`*`) resource permissions
    - Create API Gateway REST API with resources: `/summary`, `/services`, `/trend`, `/forecast`
    - Create API key and usage plan (100 req/min, burst 50)
    - Require API key on all methods
    - Configure CORS to allow `localhost` origins
    - Set CloudWatch Logs retention to 30 days on all Lambda log groups
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 4.7, 12.1, 12.2, 12.3, 12.7, 12.8_

- [ ] 12. CDK infrastructure — SchedulerStack
  - [ ] 12.1 Implement scheduler_stack.py
    - Create `cdk/stacks/scheduler_stack.py` with `SchedulerStack` class
    - Accept Ingestion Lambda ARN from ApiStack as constructor parameter
    - Create 3 EventBridge rules:
      - DAILY: `cron(0 2 * * ? *)` with event detail `{"granularity": "DAILY"}`
      - WEEKLY: `cron(0 3 ? * MON *)` with event detail `{"granularity": "WEEKLY"}`
      - MONTHLY: `cron(0 4 1 * ? *)` with event detail `{"granularity": "MONTHLY"}`
    - Grant each rule permission to invoke the Ingestion Lambda
    - _Requirements: 6.1, 6.2, 6.3_

- [ ] 13. CDK app entry point
  - [ ] 13.1 Implement cdk/app.py and cdk.json
    - Create `cdk/app.py` that instantiates DatabaseStack → ApiStack → SchedulerStack with correct dependency wiring
    - Create `cdk/cdk.json` with CDK configuration pointing to `app.py`
    - _Requirements: 5.1, 6.1_

- [ ] 14. Checkpoint — Verify CDK synth
  - Ensure `cdk synth` succeeds without errors, ask the user if questions arise.

- [ ] 15. Frontend dashboard — HTML structure and CSS theme
  - [ ] 15.1 Create index.html
    - Create `frontend/index.html` with semantic layout
    - Include header with CostWatch logo, USD/BRL pill toggle, "last synced" timestamp, pulsing green "Live" dot
    - KPI card grid (4 cards): Today's Cost, Month-to-Date, Previous Month, Forecast — each with sparkline SVG placeholder and delta badge
    - Trend chart container with Daily/Weekly/Monthly tabs
    - Top services horizontal bar chart container
    - Account breakdown donut chart container
    - Service heatmap CSS grid container
    - Budget tracker section
    - Team cost table with search input and sortable column headers
    - Load Chart.js from CDN
    - Load Google Fonts: Space Mono and DM Sans
    - Link `styles.css` and `app.js`
    - _Requirements: 7.1, 7.2, 7.4, 7.5, 8.1, 9.1, 9.3, 9.4, 9.5, 10.1, 10.3, 10.5_

  - [ ] 15.2 Create styles.css
    - Create `frontend/styles.css` with Dark Command Center theme
    - Define CSS variables: `--bg-deep: #0A0E14`, `--bg-surface: #111820`, `--bg-card: #161D27`, `--bg-card-hover: #1C2535`, `--accent-green: #00FF87`, `--accent-coral: #FF4757`, `--accent-amber: #FFB830`, `--accent-blue: #3D9DF3`, `--text-primary: #E8EDF5`, `--text-secondary: #7A8BA0`, `--text-muted: #3D4F63`, `--border: #1E2C3D`, `--border-glow: rgba(0, 255, 135, 0.15)`
    - Space Mono for headings/numbers, DM Sans for body/labels
    - KPI card hover: green glow box-shadow + 2px upward lift
    - Staggered fade-in animation (0ms, 80ms, 160ms increments)
    - Pulsing green dot animation for "Live" indicator
    - Budget progress bar colors: green (<70%), amber (70-90%), coral (>90%), "OVER BUDGET" badge (>100%)
    - Heatmap cell colors: `--bg-card` (low) → `--accent-amber` (medium) → `--accent-coral` (high)
    - Responsive grid layout for all sections
    - _Requirements: 7.3, 8.5, 10.2, 11.2, 11.3_

- [ ] 16. Frontend dashboard — Application logic
  - [ ] 16.1 Create app.js — CONFIG, API calls, and data fetching
    - Create `frontend/app.js` with `CONFIG` object (`apiBase`, `apiKey`)
    - Implement API fetch functions for each endpoint: `fetchSummary()`, `fetchServices(granularity, period)`, `fetchTrend(granularity, n)`, `fetchForecast()`
    - Include `x-api-key` header in all fetch calls
    - Handle API errors gracefully with user-visible feedback
    - _Requirements: 7.6, 4.1, 4.2, 4.3, 4.4_

  - [ ] 16.2 Implement KPI cards rendering and animations
    - Render 4 KPI cards with data from `/summary` endpoint
    - Animate each KPI number from 0 to value over 1.2s using easeOutExpo curve
    - Generate 60x24px inline sparkline SVGs from last 7 periods of data
    - Compute and display delta badges (green for improvement, coral for overspend)
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ] 16.3 Implement charts — trend line, service bars, account donut
    - Trend line chart (Chart.js): full-width, granularity tabs (Daily/Weekly/Monthly), re-fetch on tab switch with 600ms animation
    - Top 10 services horizontal bar chart: sorted descending, gradient fill accent-blue → accent-green, hover brightens bar + tooltip with % of total
    - Account breakdown donut chart: center label with animated total amount
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 11.4_

  - [ ] 16.4 Implement service heatmap
    - CSS grid: rows = top 10 services, columns = last 8 periods
    - Cell colors: `--bg-card` (low) → `--accent-amber` (medium) → `--accent-coral` (high)
    - Hover tooltip with exact cost amount and period label
    - _Requirements: 9.5, 9.6_

  - [ ] 16.5 Implement budget tracker and team cost table
    - Budget tracker: one row per account/team, animated progress bar, current spend vs budget limit
    - Progress bar colors: green (<70%), amber (70-90%), coral (>90%), "OVER BUDGET" badge (>100%)
    - Team cost table: columns — Team, Daily Average, Weekly Total, Monthly Total, % of Total, sparkline trend
    - Sortable columns (click header to toggle asc/desc)
    - Search input for real-time row filtering
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 16.6 Implement currency toggle and global animations
    - USD/BRL pill toggle: animate all displayed cost amounts from current to selected currency
    - Staggered card fade-in on page load (0ms, 80ms, 160ms increments)
    - Pulsing green "Live" dot in header
    - _Requirements: 11.1, 11.2, 11.3_

- [ ] 17. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The design uses Python throughout — all backend code uses Python 3.12, Pydantic v2, boto3, and CDK Python
- Frontend uses vanilla JS with Chart.js (CDN) — no build step required
- All AWS clients use dependency injection for testability with moto
