#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.stacks.database_stack import DatabaseStack
from cdk.stacks.api_stack import ApiStack
from cdk.stacks.scheduler_stack import SchedulerStack

app = cdk.App()

database_stack = DatabaseStack(app, "CostWatchDatabaseStack")

api_stack = ApiStack(
    app,
    "CostWatchApiStack",
    database_stack=database_stack,
)

SchedulerStack(
    app,
    "CostWatchSchedulerStack",
    ingestion_lambda=api_stack.ingest_costs_fn,
)

app.synth()
