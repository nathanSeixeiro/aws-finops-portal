from aws_cdk import Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class SchedulerStack(Stack):
    """CDK stack that provisions EventBridge rules for cost ingestion."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        ingestion_lambda: _lambda.IFunction,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        schedules = [
            ("DailyIngestion", "cron(0 2 * * ? *)", "DAILY"),
            ("WeeklyIngestion", "cron(0 3 ? * MON *)", "WEEKLY"),
            ("MonthlyIngestion", "cron(0 4 1 * ? *)", "MONTHLY"),
        ]

        for rule_id, cron_expr, granularity in schedules:
            rule = events.Rule(
                self,
                rule_id,
                schedule=events.Schedule.expression(cron_expr),
            )
            rule.add_target(
                targets.LambdaFunction(
                    ingestion_lambda,
                    event=events.RuleTargetInput.from_object(
                        {"granularity": granularity}
                    ),
                )
            )
