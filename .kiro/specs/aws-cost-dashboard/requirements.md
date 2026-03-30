# Requirements Document

## Introduction

CostWatch is a serverless AWS Cost Dashboard that provides managers with real-time and historical visibility into AWS spending across accounts, services, and teams. The system uses Python Lambdas, DynamoDB, and CDK (Python) to deploy infrastructure via the `gsti-us` AWS profile. Cost data is fetched via the AWS Cost Explorer MCP Server and stored in DynamoDB with dual-currency support (USD + BRL) at three granularities (DAILY, WEEKLY, MONTHLY). A read-only REST API is exposed via API Gateway and consumed by a locally-served frontend dashboard.

Key architectural decisions:
- No alerting or anomaly detection (no SNS, no alert Lambdas, no alert-configs table)
- No CloudFront or S3 deployment for frontend — the frontend runs locally via a live server on macOS
- 2 DynamoDB tables: `costwatch-cost-records` and `costwatch-budgets`
- 3 CDK stacks: DatabaseStack, ApiStack, SchedulerStack
- 4 API endpoints: GET /summary, GET /services, GET /trend, GET /forecast

## Glossary

- **CostWatch_System**: The complete serverless AWS Cost Dashboard application including backend Lambdas, DynamoDB tables, API Gateway, EventBridge schedules, and the locally-served frontend
- **Ingestion_Lambda**: The Lambda function (`ingest_costs.py`) triggered by EventBridge to fetch cost data from AWS Cost Explorer and store it in DynamoDB
- **Query_Lambda**: Any of the four API-facing Lambda functions (`get_summary.py`, `get_service_breakdown.py`, `get_trend.py`, `get_forecast.py`) that read from DynamoDB and return cost data
- **Cost_Record**: A single row in the `costwatch-cost-records` DynamoDB table representing cost data for one AWS service in one account for one period and granularity
- **Currency_Service**: The service module (`currency_service.py`) responsible for fetching the USD-to-BRL exchange rate from SSM Parameter Store and computing BRL amounts
- **Forecast_Service**: The service module (`forecast_service.py`) responsible for generating cost forecasts
- **Cost_Query_Service**: The service module (`cost_query_service.py`) responsible for aggregating and filtering cost data from DynamoDB
- **Cost_Ingestion_Service**: The service module (`cost_ingestion_service.py`) responsible for orchestrating cost data fetching and storage
- **API_Gateway**: The AWS API Gateway REST API that exposes the four read-only endpoints with API key authentication
- **Dashboard_Frontend**: The locally-served single-page application (index.html, app.js, styles.css) that consumes the API and renders the "Dark Command Center" UI
- **EventBridge_Scheduler**: The set of three EventBridge rules that trigger the Ingestion_Lambda at daily, weekly, and monthly intervals
- **DatabaseStack**: The CDK stack that provisions the two DynamoDB tables with GSIs, TTL, and PITR
- **ApiStack**: The CDK stack that provisions the API Gateway, Lambda functions, and per-Lambda IAM roles
- **SchedulerStack**: The CDK stack that provisions the three EventBridge rules for cost ingestion
- **Granularity**: One of three time resolutions for cost data: `DAILY`, `WEEKLY`, or `MONTHLY`
- **Period**: The time range a Cost_Record covers, formatted as `YYYY-MM-DD` for DAILY/WEEKLY or `YYYY-MM` for MONTHLY
- **SSM_Parameter_Store**: AWS Systems Manager Parameter Store, used to store the BRL exchange rate as a SecureString at path `/costwatch/brl-exchange-rate`
- **MCP_Server**: The AWS Cost Explorer MCP Server (`awslabs.cost-explorer-mcp-server`) used to fetch cost data from AWS Cost Explorer
- **Budget**: A monthly spending threshold stored in the `costwatch-budgets` DynamoDB table, associated with an account or team

## Requirements

### Requirement 1: Cost Data Ingestion

**User Story:** As a manager, I want AWS cost data to be automatically ingested at daily, weekly, and monthly intervals, so that the dashboard always reflects up-to-date spending information.

#### Acceptance Criteria

1. WHEN the EventBridge_Scheduler triggers with `{"granularity": "DAILY"}` at 02:00 UTC every day, THE Ingestion_Lambda SHALL fetch the previous day's cost data from the MCP_Server and store Cost_Records in DynamoDB with period format `YYYY-MM-DD`
2. WHEN the EventBridge_Scheduler triggers with `{"granularity": "WEEKLY"}` at 03:00 UTC every Monday, THE Ingestion_Lambda SHALL fetch the previous ISO week's (Monday through Sunday) cost data from the MCP_Server and store Cost_Records in DynamoDB with period format `YYYY-MM-DD` (week start date)
3. WHEN the EventBridge_Scheduler triggers with `{"granularity": "MONTHLY"}` at 04:00 UTC on the 1st of every month, THE Ingestion_Lambda SHALL fetch the previous full month's cost data from the MCP_Server and store Cost_Records in DynamoDB with period format `YYYY-MM`
4. WHEN the Ingestion_Lambda stores a Cost_Record, THE Cost_Ingestion_Service SHALL set the partition key as `ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}` and the sort key as `SERVICE#{service_name}`
5. WHEN the Ingestion_Lambda stores a Cost_Record, THE Cost_Ingestion_Service SHALL include both `amount_usd` and `amount_brl` values (each with 4 decimal places), the `exchange_rate` used, and an `ingested_at` ISO 8601 timestamp
6. WHEN the Ingestion_Lambda stores a DAILY Cost_Record, THE Cost_Ingestion_Service SHALL set the TTL to 365 days from ingestion
7. WHEN the Ingestion_Lambda stores a WEEKLY Cost_Record, THE Cost_Ingestion_Service SHALL set the TTL to 2 years from ingestion
8. WHEN the Ingestion_Lambda stores a MONTHLY Cost_Record, THE Cost_Ingestion_Service SHALL set the TTL to 5 years from ingestion
9. IF the MCP_Server is unreachable or returns an error during ingestion, THEN THE Ingestion_Lambda SHALL log the error with the granularity and period context and exit without writing partial data to DynamoDB

### Requirement 2: Currency Conversion

**User Story:** As a manager, I want all cost data stored and displayed in both USD and BRL, so that I can view spending in my preferred currency.

#### Acceptance Criteria

1. WHEN the Ingestion_Lambda processes cost data, THE Currency_Service SHALL fetch the USD-to-BRL exchange rate from SSM_Parameter_Store at path `/costwatch/brl-exchange-rate`
2. WHEN the Currency_Service retrieves the exchange rate, THE Currency_Service SHALL compute `amount_brl` by multiplying `amount_usd` by the exchange rate and rounding to 4 decimal places
3. WHEN the Currency_Service stores a Cost_Record, THE Currency_Service SHALL persist the `exchange_rate` value used for the conversion alongside `amount_usd` and `amount_brl`
4. IF the SSM_Parameter_Store is unreachable or the parameter is missing, THEN THE Currency_Service SHALL use a configurable fallback exchange rate and log a warning
5. THE API_Gateway SHALL return both `amount_usd` and `amount_brl` in every cost-related API response payload

### Requirement 3: DynamoDB Table Design

**User Story:** As a developer, I want the DynamoDB tables to be provisioned with the correct schema, indexes, and settings, so that cost data can be efficiently queried across multiple access patterns.

#### Acceptance Criteria

1. THE DatabaseStack SHALL create a `costwatch-cost-records` table with partition key `pk` (String) and sort key `sk` (String) using PAY_PER_REQUEST billing mode
2. THE DatabaseStack SHALL create GSI `gsi-gran-period` on the `costwatch-cost-records` table with partition key `granularity` (String) and sort key `period` (String)
3. THE DatabaseStack SHALL create GSI `gsi-service-period` on the `costwatch-cost-records` table with partition key `service_name` (String) and sort key `period` (String)
4. THE DatabaseStack SHALL create GSI `gsi-account-gran` on the `costwatch-cost-records` table with partition key `account_id` (String) and sort key as composite `granularity#period` (String)
5. THE DatabaseStack SHALL enable TTL on the `costwatch-cost-records` table using the `ttl` attribute
6. THE DatabaseStack SHALL enable point-in-time recovery on the `costwatch-cost-records` table
7. THE DatabaseStack SHALL enable encryption at rest using AWS_OWNED_KEY on the `costwatch-cost-records` table
8. THE DatabaseStack SHALL create a `costwatch-budgets` table with partition key `pk` (String) and sort key `sk` (String) using PAY_PER_REQUEST billing mode
9. THE DatabaseStack SHALL enable encryption at rest using AWS_OWNED_KEY on the `costwatch-budgets` table
10. THE DatabaseStack SHALL export table names and ARNs as CloudFormation outputs

### Requirement 4: REST API Endpoints

**User Story:** As a manager, I want to query cost data through a REST API, so that the frontend dashboard can display summaries, breakdowns, trends, and forecasts.

#### Acceptance Criteria

1. WHEN a GET request is made to `/summary` with a valid `x-api-key` header, THE Query_Lambda SHALL return the current day's total cost, month-to-date total, previous month total, and forecast amount in both USD and BRL
2. WHEN a GET request is made to `/services` with query parameters `granularity`, `period`, and `currency`, THE Query_Lambda SHALL return a list of AWS services with their cost amounts for the specified granularity and period, sorted descending by amount
3. WHEN a GET request is made to `/trend` with query parameters `granularity`, `n` (number of periods), and `currency`, THE Query_Lambda SHALL return cost totals for the last `n` periods at the specified granularity in both USD and BRL
4. WHEN a GET request is made to `/forecast` with an optional `currency` query parameter, THE Query_Lambda SHALL return a projected cost for the current month based on historical spending patterns in both USD and BRL
5. IF a request is made to any endpoint without a valid `x-api-key` header, THEN THE API_Gateway SHALL return HTTP 401 Unauthorized
6. IF a request is made with invalid or missing query parameters, THEN THE Query_Lambda SHALL return HTTP 400 Bad Request with a descriptive error message
7. THE API_Gateway SHALL enforce a usage plan of 100 requests per minute with a burst limit of 50 requests

### Requirement 5: API Gateway and Lambda Infrastructure

**User Story:** As a developer, I want the API Gateway and Lambda functions provisioned via CDK with proper IAM roles, so that each function has least-privilege access to only the resources it needs.

#### Acceptance Criteria

1. THE ApiStack SHALL create one Lambda function per handler: `get_summary`, `get_service_breakdown`, `get_trend`, and `get_forecast`
2. THE ApiStack SHALL assign each Query_Lambda its own IAM role with read-only DynamoDB permissions (`GetItem`, `Query`) scoped to the specific tables the Lambda accesses
3. THE ApiStack SHALL assign the Ingestion_Lambda its own IAM role with `ce:GetCostAndUsage`, `ce:GetCostForecast` permissions, DynamoDB `PutItem`/`UpdateItem` on the `costwatch-cost-records` table, and SSM `GetParameter` for `/costwatch/brl-exchange-rate`
4. THE ApiStack SHALL create an API Gateway REST API with an API key and associated usage plan
5. THE ApiStack SHALL pass DynamoDB table names and SSM parameter paths as environment variables to each Lambda function
6. THE ApiStack SHALL configure CORS to allow requests from `localhost` origins for local frontend development

### Requirement 6: EventBridge Scheduling

**User Story:** As a developer, I want EventBridge rules to trigger cost ingestion on the correct schedules, so that data is fetched at the right cadence for each granularity.

#### Acceptance Criteria

1. THE SchedulerStack SHALL create an EventBridge rule that triggers the Ingestion_Lambda every day at 02:00 UTC with event detail `{"granularity": "DAILY"}`
2. THE SchedulerStack SHALL create an EventBridge rule that triggers the Ingestion_Lambda every Monday at 03:00 UTC with event detail `{"granularity": "WEEKLY"}`
3. THE SchedulerStack SHALL create an EventBridge rule that triggers the Ingestion_Lambda on the 1st of every month at 04:00 UTC with event detail `{"granularity": "MONTHLY"}`

### Requirement 7: Frontend Dashboard — Visual Design

**User Story:** As a manager, I want a visually striking "Dark Command Center" dashboard served locally on my Mac, so that I can monitor AWS costs with a polished, information-dense interface.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL consist of three files: `index.html`, `app.js`, and `styles.css` served via a local live server on macOS
2. THE Dashboard_Frontend SHALL use `Space Mono` (Google Fonts) for headings and cost numbers, and `DM Sans` for body text and labels
3. THE Dashboard_Frontend SHALL define CSS variables for the dark theme palette: `--bg-deep: #0A0E14`, `--bg-surface: #111820`, `--bg-card: #161D27`, `--bg-card-hover: #1C2535`, `--accent-green: #00FF87`, `--accent-coral: #FF4757`, `--accent-amber: #FFB830`, `--accent-blue: #3D9DF3`, `--text-primary: #E8EDF5`, `--text-secondary: #7A8BA0`, `--text-muted: #3D4F63`, `--border: #1E2C3D`, `--border-glow: rgba(0, 255, 135, 0.15)`
4. THE Dashboard_Frontend SHALL include a header with the CostWatch logo, a USD/BRL pill toggle, and a "last synced" timestamp
5. THE Dashboard_Frontend SHALL use Chart.js loaded from CDN for rendering trend line charts, donut charts, and horizontal bar charts
6. THE Dashboard_Frontend SHALL include a `CONFIG` object at the top of `app.js` with `apiBase` and `apiKey` properties pointing to the API Gateway URL

### Requirement 8: Frontend Dashboard — KPI Cards

**User Story:** As a manager, I want four KPI cards showing today's cost, month-to-date, previous month, and forecast, so that I can see key spending metrics at a glance.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL display four KPI cards: Today's Cost, Month-to-Date, Previous Month Total, and Forecast
2. WHEN the Dashboard_Frontend loads, THE Dashboard_Frontend SHALL animate each KPI number from 0 to its value over 1.2 seconds using an easeOutExpo curve
3. THE Dashboard_Frontend SHALL display a 60px by 24px inline sparkline SVG in each KPI card showing the last 7 periods of data
4. THE Dashboard_Frontend SHALL display a delta badge on each KPI card showing the percentage change versus the previous period, colored green for improvement and coral for overspend
5. WHEN the user hovers over a KPI card, THE Dashboard_Frontend SHALL apply a green glow box-shadow and a 2px upward lift transition

### Requirement 9: Frontend Dashboard — Charts and Visualizations

**User Story:** As a manager, I want interactive charts showing cost trends, service breakdowns, and account distributions, so that I can analyze spending patterns visually.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL display a full-width trend line chart with tabs for Daily, Weekly, and Monthly granularity
2. WHEN the user switches granularity tabs on the trend chart, THE Dashboard_Frontend SHALL re-fetch data from the API and animate the chart transition over 600 milliseconds
3. THE Dashboard_Frontend SHALL display a horizontal bar chart of the top 10 services sorted descending by cost amount, with a gradient fill from accent-blue to accent-green
4. THE Dashboard_Frontend SHALL display an account breakdown donut chart with a center label showing the animated total amount
5. THE Dashboard_Frontend SHALL display a service heatmap as a CSS grid with rows for the top 10 services and columns for the last 8 periods, with cell colors ranging from `--bg-card` (low cost) through `--accent-amber` (medium) to `--accent-coral` (high cost)
6. WHEN the user hovers over a heatmap cell, THE Dashboard_Frontend SHALL display a tooltip with the exact cost amount and period label

### Requirement 10: Frontend Dashboard — Budget Tracker and Team Table

**User Story:** As a manager, I want to see budget progress and team-level cost breakdowns, so that I can track spending against budgets and identify team-level cost drivers.

#### Acceptance Criteria

1. THE Dashboard_Frontend SHALL display a budget tracker section with one row per account or team showing an animated progress bar and the current spend versus budget limit
2. THE Dashboard_Frontend SHALL color budget progress bars green when below 70%, amber between 70% and 90%, and coral above 90%, with an "OVER BUDGET" badge when exceeding 100%
3. THE Dashboard_Frontend SHALL display a team cost table with columns: Team, Daily Average, Weekly Total, Monthly Total, Percentage of Total, and a sparkline trend
4. WHEN the user clicks a column header in the team cost table, THE Dashboard_Frontend SHALL sort the table by that column in ascending or descending order
5. THE Dashboard_Frontend SHALL include a search input above the team cost table that filters rows in real time as the user types

### Requirement 11: Frontend Dashboard — Currency Toggle and Animations

**User Story:** As a manager, I want to toggle between USD and BRL display and see smooth animations throughout the dashboard, so that the experience feels polished and responsive.

#### Acceptance Criteria

1. WHEN the user clicks the USD/BRL pill toggle in the header, THE Dashboard_Frontend SHALL animate all displayed cost amounts from the current currency to the selected currency
2. WHEN the Dashboard_Frontend loads, THE Dashboard_Frontend SHALL fade in all cards with staggered animation delays (0ms, 80ms, 160ms increments)
3. THE Dashboard_Frontend SHALL display a pulsing green dot with "Live" text in the header as a live indicator
4. WHEN the user hovers over a bar in the top services chart, THE Dashboard_Frontend SHALL brighten the bar and display a tooltip showing the percentage of total spend

### Requirement 12: Security

**User Story:** As a developer, I want the system to follow security best practices, so that cost data is protected and access is controlled.

#### Acceptance Criteria

1. THE ApiStack SHALL assign each Lambda function its own IAM role with no wildcard (`*`) resource permissions
2. THE API_Gateway SHALL require a valid `x-api-key` header on every request
3. THE API_Gateway SHALL enforce HTTPS-only (TLS 1.2+) for all API traffic
4. THE DatabaseStack SHALL enable encryption at rest on all DynamoDB tables using AWS_OWNED_KEY
5. THE DatabaseStack SHALL enable point-in-time recovery on the `costwatch-cost-records` table
6. THE CostWatch_System SHALL store the BRL exchange rate in SSM_Parameter_Store as a SecureString
7. THE ApiStack SHALL configure CORS allowed origins to include only `localhost` for local development
8. THE CostWatch_System SHALL set CloudWatch Logs retention to 30 days on all Lambda log groups

### Requirement 13: Pydantic Data Models

**User Story:** As a developer, I want strongly-typed Pydantic v2 models for all data structures, so that data validation is consistent and type-safe across the application.

#### Acceptance Criteria

1. THE CostWatch_System SHALL define a `CostRecord` Pydantic v2 model with fields: `pk` (str), `sk` (str), `account_id` (str), `account_alias` (str), `period` (str), `period_end` (str), `granularity` (Literal["DAILY", "WEEKLY", "MONTHLY"]), `service_name` (str), `amount_usd` (Decimal), `amount_brl` (Decimal), `exchange_rate` (Decimal), `tags` (dict), `ingested_at` (str), `ttl` (int)
2. THE CostWatch_System SHALL define a `ServiceBreakdown` Pydantic v2 model with fields for service name, cost amounts in both currencies, and percentage of total
3. THE CostWatch_System SHALL define a `Budget` Pydantic v2 model with fields: `pk` (str), `sk` (str), `budget_usd` (Decimal), `budget_brl` (Decimal), `alert_threshold_pct` (Decimal), `owner_email` (str), `created_at` (str), `updated_at` (str)

### Requirement 14: Repository Layer

**User Story:** As a developer, I want a repository layer that encapsulates all DynamoDB access using the exact key patterns from the table specification, so that data access is consistent and testable.

#### Acceptance Criteria

1. THE CostWatch_System SHALL implement a `cost_record_repository.py` that uses the partition key pattern `ACCOUNT#{account_id}#GRAN#{granularity}#PERIOD#{period}` and sort key pattern `SERVICE#{service_name}` for all DynamoDB operations on the `costwatch-cost-records` table
2. THE CostWatch_System SHALL implement a `budget_repository.py` that uses the partition key pattern `ACCOUNT#{account_id}` or `TEAM#{team_name}` and sort key `BUDGET#MONTHLY` for all DynamoDB operations on the `costwatch-budgets` table
3. THE CostWatch_System SHALL support querying the `costwatch-cost-records` table via GSI `gsi-gran-period`, `gsi-service-period`, and `gsi-account-gran`
4. THE CostWatch_System SHALL use dependency injection for all AWS clients in the repository layer to enable unit testing with mocked clients

### Requirement 15: Service Layer

**User Story:** As a developer, I want a service layer that orchestrates business logic separately from Lambda handlers, so that the code is modular and testable.

#### Acceptance Criteria

1. THE Cost_Ingestion_Service SHALL handle all three granularities (DAILY, WEEKLY, MONTHLY) by parsing the EventBridge event detail and computing the correct period format and TTL
2. THE Cost_Query_Service SHALL accept a `granularity` parameter and aggregate cost data across accounts and services for the requested time range
3. THE Forecast_Service SHALL generate a projected monthly cost based on historical spending patterns
4. THE Currency_Service SHALL fetch the exchange rate from SSM_Parameter_Store, compute BRL amounts, and cache the rate for the duration of a single Lambda invocation
5. THE CostWatch_System SHALL keep Lambda handlers as thin wrappers that delegate to the service layer with no business logic in the handler files

### Requirement 16: Testing

**User Story:** As a developer, I want comprehensive unit tests using pytest and moto, so that all components are verified without making real AWS calls.

#### Acceptance Criteria

1. THE CostWatch_System SHALL use pytest with moto for mocking DynamoDB and SSM in all unit tests
2. THE CostWatch_System SHALL achieve greater than 80% code coverage across the `src/` directory
3. THE CostWatch_System SHALL include unit tests for all Lambda handlers, services, repositories, and utility modules
4. THE CostWatch_System SHALL test the `auth.py` utility for three cases: missing API key returns HTTP 401, invalid API key returns HTTP 401, and valid API key allows the request to proceed
5. THE CostWatch_System SHALL test the `response.py` utility to verify the response envelope includes both `amount_usd` and `amount_brl` fields
6. THE CostWatch_System SHALL test the Currency_Service for SSM rate fetch, BRL conversion accuracy, and fallback behavior when SSM is unavailable
7. THE CostWatch_System SHALL use dependency injection for all AWS clients to enable testing without real AWS calls

### Requirement 17: Tooling and Project Configuration

**User Story:** As a developer, I want standardized project tooling with pyproject.toml, .mise.toml, and a Makefile, so that the development workflow is consistent and reproducible.

#### Acceptance Criteria

1. THE CostWatch_System SHALL use a `pyproject.toml` with `uv` as the package manager, declaring dependencies: pydantic (>=2.0), boto3 (>=1.34), aws-cdk-lib (>=2.140), constructs (>=10.0), and requests (>=2.31)
2. THE CostWatch_System SHALL use a `.mise.toml` configuring Python 3.12, Node 20, and aws-cdk (latest), with `AWS_PROFILE` set to `gsti-us`
3. THE CostWatch_System SHALL include a Makefile with targets: `deploy` (CDK deploy with `gsti-us` profile), `unit-testing` (pytest with coverage), `lint` (ruff check), `format` (ruff format), `install` (uv sync), `bootstrap` (CDK bootstrap), `synth` (CDK synth), and `diff` (CDK diff)

### Requirement 18: MCP Server Configuration

**User Story:** As a developer, I want the AWS Cost Explorer MCP Server configured in the project, so that the ingestion Lambda can fetch cost data from AWS Cost Explorer.

#### Acceptance Criteria

1. THE CostWatch_System SHALL include a `.kiro/mcp.json` file configuring the `awslabs.cost-explorer-mcp-server` with `uvx` as the command, `AWS_PROFILE` set to `gsti-us`, and `FASTMCP_LOG_LEVEL` set to `ERROR`
