from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_sources,
    aws_apigateway as apigw,
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

        # --------------------
        # S3 (optional assets)
        # --------------------
        s3.Bucket(self, "TestBucket")

        # --------------------
        # DynamoDB (with Streams)
        # --------------------
        exercises_table = dynamodb.Table(
            self,
            "ExercisesTable",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            removal_policy=RemovalPolicy.DESTROY,  # local/dev only
        )

        # --------------------
        # SNS -> SQS
        # --------------------
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

        # SQS -> Lambda
        generator_fn.add_event_source(
            lambda_sources.SqsEventSource(generation_queue)
        )

        # DynamoDB Streams -> Lambda
        watcher_fn.add_event_source(
            lambda_sources.DynamoEventSource(
                exercises_table,
                starting_position=_lambda.StartingPosition.LATEST,
            )
        )

        # --------------------
        # API Gateway (6.4)
        # --------------------
        api = apigw.RestApi(
            self,
            "Api",
            rest_api_name="AIC-Api",
            description="AIC Project API (Stage 1 skeleton)",
        )

        # GET /health -> watcher_fn
        health = api.root.add_resource("health")
        health.add_method(
            "GET",
            apigw.LambdaIntegration(watcher_fn),
        )

        # POST /generate -> generator_fn
        generate = api.root.add_resource("generate")
        generate.add_method(
            "POST",
            apigw.LambdaIntegration(generator_fn),
        )
