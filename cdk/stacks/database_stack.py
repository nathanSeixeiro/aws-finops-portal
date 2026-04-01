from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class DatabaseStack(Stack):
    """CDK stack that provisions the two DynamoDB tables for CostWatch."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── costwatch-cost-records table ──────────────────────────────
        self.cost_records_table = dynamodb.Table(
            self,
            "CostRecordsTable",
            table_name="costwatch-cost-records",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI: gsi-gran-period
        self.cost_records_table.add_global_secondary_index(
            index_name="gsi-gran-period",
            partition_key=dynamodb.Attribute(name="granularity", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="period", type=dynamodb.AttributeType.STRING),
        )

        # GSI: gsi-service-period
        self.cost_records_table.add_global_secondary_index(
            index_name="gsi-service-period",
            partition_key=dynamodb.Attribute(name="service_name", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="period", type=dynamodb.AttributeType.STRING),
        )

        # GSI: gsi-account-gran (composite SK: granularity#period)
        self.cost_records_table.add_global_secondary_index(
            index_name="gsi-account-gran",
            partition_key=dynamodb.Attribute(name="account_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="account_gran_sk", type=dynamodb.AttributeType.STRING),
        )

        # ── costwatch-budgets table ───────────────────────────────────
        self.budgets_table = dynamodb.Table(
            self,
            "BudgetsTable",
            table_name="costwatch-budgets",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ── CloudFormation outputs ────────────────────────────────────
        CfnOutput(self, "CostRecordsTableName", value=self.cost_records_table.table_name)
        CfnOutput(self, "CostRecordsTableArn", value=self.cost_records_table.table_arn)
        CfnOutput(self, "BudgetsTableName", value=self.budgets_table.table_name)
        CfnOutput(self, "BudgetsTableArn", value=self.budgets_table.table_arn)
