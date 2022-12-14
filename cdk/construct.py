from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_lambda_event_sources as event_source,
    aws_logs as logs,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_cloudfront as cloudfront,
    aws_s3_deployment as deployment,
    aws_cloudfront_origins as origins,
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
            timeout=Duration.seconds(60),
            environment=self.node.try_get_context(f"env_fn_{id}"),
            memory_size=256,
        )

        loggroup_name = f"/aws/lambda/{self.fn.function_name}"
        logs.LogGroup(
            self, f"{id}-loggroup",
            log_group_name=loggroup_name,
            retention=logs.RetentionDays.ONE_DAY,
        )


class DockerLambdaWithoutLayer(Construct):

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        function_name = f"lmd-{id}-cdk"

        self.fn = lambda_.DockerImageFunction(
            self, function_name,
            code=lambda_.DockerImageCode.from_image_asset(
                directory=f"src/{id}",
            ),
            function_name=function_name,
            environment=self.node.try_get_context(f"env_fn_{id}"),
            timeout=cdk.Duration.seconds(60),
            memory_size=2048,
        )

        loggroup_name = f"/aws/lambda/{self.fn.function_name}"
        logs.LogGroup(
            self, f"{id}-loggroup",
            log_group_name=loggroup_name,
            retention=logs.RetentionDays.ONE_DAY,
        )

class LambdaToSqsToLambda(Construct):

    def __init__(self, scope: Construct, id: str, target_fn: lambda_.Function) -> None:
        super().__init__(scope, id)

        queue_name = f"sqs-{id}-cdk"

        self.queue = sqs.Queue(
            self, queue_name,
            queue_name=queue_name,
            visibility_timeout=Duration.seconds(60),
        )

        lambda_construct = PythonLambdaWithoutLayer(self, id)
        self.fn = lambda_construct.fn

        target_fn.add_event_source(event_source.SqsEventSource(self.queue))
        self.fn.add_environment(f"{id.upper()}_URL", self.queue.queue_url)
        self.queue.grant_send_messages(self.fn)


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
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        for fn in fns:
            fn.add_environment(
                f"{id.upper()}_TABLE_NAME", self.db.table_name)
            fn.add_environment(f"{id.upper()}_TABLE_PKEY", pkey)
            fn.add_environment(f"{id.upper()}_TABLE_SKEY", skey)


class CreateBucketAndSetEnvToFn(Construct):

    def __init__(self, scope: Construct, id: str, fns: list[lambda_.Function] = []) -> None:
        super().__init__(scope, id)

        bucket_name = f"s3s-{id.replace('_', '-').lower()}-cdk"
        key = self.node.try_get_context(f"env_s3_{id.lower()}")["key"]

        self.bucket = s3.Bucket(
            self, bucket_name,
            bucket_name=bucket_name,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="result_delete",
                    prefix=key,
                    expiration=Duration.days(1),
                ),
            ]
        )

        for fn in fns:
            fn.add_environment(
                f"{id.upper()}_BUCKET_NAME", self.bucket.bucket_name)
            fn.add_environment(f"{id.upper()}_BUCKET_KEY", key)

class StaticWebSite(Construct):

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        bucket_name = f"s3s-pub-{id}-cdk"

        website_bucket = s3.Bucket(
            self, bucket_name,
            bucket_name=bucket_name,
        )

        website_distribution = cloudfront.Distribution(
            self, f"clf_{id}_WebDistribution_cdk",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(website_bucket)
            )
        )

        deployment.BucketDeployment(
            self, f"dep_{id}_cdk",
            sources=[deployment.Source.asset("static")],
            destination_bucket=website_bucket,
            distribution=website_distribution,
            distribution_paths=["/*"]
        )

        cdk.CfnOutput(
            self, "static_web_site_url",
            value=f"https://{website_distribution.domain_name}"
        )