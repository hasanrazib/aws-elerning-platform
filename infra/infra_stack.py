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
    aws_cognito as cognito,
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

                # --------------------
        # Cognito (6.5)
        # --------------------
        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="aic-user-pool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,  # local/dev only
        )

        user_pool_client = user_pool.add_client(
            "UserPoolClient",
            auth_flows=cognito.AuthFlow(user_password=True),
            generate_secret=False,
        )

