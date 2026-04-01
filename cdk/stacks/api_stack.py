from aws_cdk import (
    BundlingOptions,
    Duration,
    ILocalBundling,
    Stack,
)
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
import jsii
from constructs import Construct

from cdk.stacks.database_stack import DatabaseStack


@jsii.implements(ILocalBundling)
class LocalBundler:
    def try_bundle(self, output_dir: str, *, image, entrypoint=None, volumes=None, working_directory=None, user=None, local=None, output_type=None, security_opt=None, network=None, bundling_file_access=None, command=None, environment=None) -> bool:
        import shutil
        import subprocess

        subprocess.check_call([
            "pip", "install", "pydantic", "requests",
            "-t", output_dir, "--quiet",
            "--platform", "manylinux2014_x86_64",
            "--only-binary=:all:",
            "--python-version", "3.12",
            "--implementation", "cp",
        ])
        src_dir = "src"
        for item in __import__("os").listdir(src_dir):
            s = __import__("os").path.join(src_dir, item)
            d = __import__("os").path.join(output_dir, item)
            if __import__("os").path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        return True


class ApiStack(Stack):
    """CDK stack: API Gateway + 2 Lambdas (ingest + dashboard)."""

    SSM_BRL_RATE_PATH = "/costwatch/brl-exchange-rate"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        database_stack: DatabaseStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cost_records_table = database_stack.cost_records_table
        # Keep budgets_table reference to avoid breaking cross-stack export
        budgets_table = database_stack.budgets_table  # noqa: F841

        api_key_value = "8V9asI6yRD6oFPIx0vJWca6b2F3wOyoXf1hJSL3g"

        common_env = {
            "COST_RECORDS_TABLE": cost_records_table.table_name,
            "BUDGETS_TABLE": budgets_table.table_name,
            "SSM_BRL_RATE_PATH": self.SSM_BRL_RATE_PATH,
            "API_KEY": api_key_value,
        }

        lambda_code = _lambda.Code.from_asset(
            "src",
            bundling=BundlingOptions(
                image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                command=["bash", "-c", "echo 'skipped'"],
                local=LocalBundler(),
            ),
        )

        def _make_lambda(id: str, handler: str, timeout: int = 30) -> _lambda.Function:
            fn = _lambda.Function(
                self, id,
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler=handler,
                code=lambda_code,
                environment=common_env,
                timeout=Duration.seconds(timeout),
            )
            logs.LogGroup(
                self, f"{id}LogGroup",
                log_group_name=f"/aws/lambda/{fn.function_name}",
                retention=logs.RetentionDays.ONE_MONTH,
            )
            return fn

        # ── Lambdas ──────────────────────────────────────────────────
        self.ingest_costs_fn = _make_lambda(
            "IngestCostsFunction", "handlers.ingest_costs.handler", timeout=120,
        )

        self.get_dashboard_fn = _make_lambda(
            "GetDashboardFunction", "handlers.get_dashboard.handler",
        )

        # ── IAM: Ingestion (read+write for costs + snapshot) ─────────
        cost_records_table.grant_read_write_data(self.ingest_costs_fn)
        self.ingest_costs_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ce:GetCostAndUsage", "ce:GetCostForecast"],
                resources=["*"],
            )
        )
        self.ingest_costs_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    self.format_arn(
                        service="ssm",
                        resource="parameter",
                        resource_name="costwatch/brl-exchange-rate",
                    )
                ],
            )
        )

        # ── IAM: Dashboard (read-only, just GetItem) ─────────────────
        cost_records_table.grant_read_data(self.get_dashboard_fn)

        # ── API Gateway ──────────────────────────────────────────────
        api = apigw.RestApi(
            self, "CostWatchApi",
            rest_api_name="CostWatch API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=["http://localhost:5500", "http://127.0.0.1:5500",
                               "http://localhost:3000", "http://127.0.0.1:3000",
                               "http://localhost:8080", "http://127.0.0.1:8080"],
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "x-api-key"],
            ),
        )

        api_key = api.add_api_key("CostWatchApiKey", value=api_key_value)
        plan = api.add_usage_plan(
            "CostWatchUsagePlan",
            name="CostWatchUsagePlan",
            throttle=apigw.ThrottleSettings(rate_limit=100, burst_limit=50),
        )
        plan.add_api_key(api_key)
        plan.add_api_stage(stage=api.deployment_stage)

        # Single endpoint — all dashboard data in one call
        dashboard_resource = api.root.add_resource("dashboard")
        dashboard_resource.add_method(
            "GET",
            apigw.LambdaIntegration(self.get_dashboard_fn),
            api_key_required=True,
        )
