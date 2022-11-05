from __future__ import annotations

from aws_cdk import (
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_dynamodb as dynamodb,
    Duration,
)
from constructs import Construct


class PythonLambdaWithoutLayer(Construct):

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        function_name = f"lmd-{id}-cdk"

        self.fn = lambda_.Function(
            self, function_name,
            function_name=function_name,
            code=lambda_.Code.from_asset(f"src/{id}"),
            handler="lambda_function.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(10),
            environment=self.node.try_get_context(f"env_fn_{id}"),
            memory_size=256,
        )

        loggroup_name = f"/aws/lambda/{self.fn.function_name}"
        logs.LogGroup(
            self, f"{id}-loggroup",
            log_group_name=loggroup_name,
            retention=logs.RetentionDays.ONE_DAY,
        )


class CreateDbAndSetEnvToFn(Construct):

    def __init__(self, scope: Construct, id: str, fns: list[lambda_.Function] = []) -> None:
        super().__init__(scope, id)

        table_name = f"dyn-{id}-cdk"

        pkey = self.node.try_get_context(f"env_db_{id.lower()}")["pkey"]
        skey = self.node.try_get_context(f"env_db_{id.lower()}")["skey"]

        self.db = dynamodb.Table(
            self, table_name,
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name=pkey,
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name=skey,
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PROVISIONED,
            read_capacity=1,
            write_capacity=1,
        )

        for fn in fns:
            fn.add_environment(
                f"{id.upper()}_TABLE_NAME", self.db.table_name)
            fn.add_environment(f"{id.upper()}_TABLE_PKEY", pkey)
            fn.add_environment(f"{id.upper()}_TABLE_SKEY", skey)
