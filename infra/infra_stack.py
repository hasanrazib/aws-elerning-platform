from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_sources,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_sns_subscriptions as subs,
)
from constructs import Construct


class InfraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 (smoke test / optional profile pics later)
        s3.Bucket(self, "TestBucket")

        # DynamoDB with Streams (needed later for watcher)
        exercises_table = dynamodb.Table(
            self,
            "ExercisesTable",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            removal_policy=RemovalPolicy.DESTROY,  # local/dev only
        )

        # SNS -> SQS (async messaging skeleton)
        generation_topic = sns.Topic(self, "GenerationTopic")

        generation_queue = sqs.Queue(
            self,
            "GenerationQueue",
            visibility_timeout=Duration.seconds(30),
        )

        generation_topic.add_subscription(
            subs.SqsSubscription(generation_queue)
        )

        # --------------------
        # Lambda stubs
        # --------------------

        generator_fn = _lambda.Function(
            self,
            "GeneratorFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="generator.handler",
            code=_lambda.Code.from_asset("lambda"),
        )

        watcher_fn = _lambda.Function(
            self,
            "WatcherFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="watcher.handler",
            code=_lambda.Code.from_asset("lambda"),
        )

        # SQS -> Lambda (generator)
        generator_fn.add_event_source(
            lambda_sources.SqsEventSource(generation_queue)
        )

        # DynamoDB Streams -> Lambda (watcher)
        watcher_fn.add_event_source(
            lambda_sources.DynamoEventSource(
                exercises_table,
                starting_position=_lambda.StartingPosition.LATEST,
            )
        )
