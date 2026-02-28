"""Full CDK stack for Quantum DNS Shield (Option 2.5).

Deploys: VPC, ALB (HTTP or HTTPS), ECS Fargate, ElastiCache Redis,
Lambda QRNG generator, S3 audit bucket, Secrets Manager, CloudWatch.
"""

from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_certificatemanager as acm,
    aws_cloudwatch as cloudwatch,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_ecs as ecs,
    aws_elasticache as elasticache,
    aws_elasticloadbalancingv2 as elbv2,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class QuantumDNSStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Optional HTTPS: pass -c certificate_arn=arn:aws:acm:...
        certificate_arn = self.node.try_get_context("certificate_arn")

        # ── VPC ──────────────────────────────────────────────────────
        vpc = ec2.Vpc(
            self,
            "VPC",
            max_azs=1,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC),
                ec2.SubnetConfiguration(
                    name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
            ],
        )

        # VPC Endpoints
        vpc.add_gateway_endpoint("S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3)
        vpc.add_interface_endpoint(
            "SecretsEndpoint", service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER
        )
        vpc.add_interface_endpoint(
            "LogsEndpoint", service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS
        )

        # ── Security Groups ──────────────────────────────────────────
        sg_alb = ec2.SecurityGroup(self, "SGAlb", vpc=vpc, description="ALB")
        sg_app = ec2.SecurityGroup(self, "SGApp", vpc=vpc, description="ECS tasks")
        sg_redis = ec2.SecurityGroup(self, "SGRedis", vpc=vpc, description="Redis")
        sg_lambda = ec2.SecurityGroup(self, "SGLambda", vpc=vpc, description="Lambda")

        # ALB inbound
        sg_alb.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")
        sg_alb.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")

        # App from ALB
        sg_app.add_ingress_rule(sg_alb, ec2.Port.tcp(8501), "Streamlit from ALB")
        sg_app.add_ingress_rule(sg_alb, ec2.Port.tcp(8000), "FastAPI from ALB")

        # Redis from app + lambda
        sg_redis.add_ingress_rule(sg_app, ec2.Port.tcp(6379), "Redis from ECS")
        sg_redis.add_ingress_rule(sg_lambda, ec2.Port.tcp(6379), "Redis from Lambda")

        # ── Secrets Manager ──────────────────────────────────────────
        ibm_token = secretsmanager.Secret(
            self, "IBMToken", secret_name="quantum-dns/ibm-token"
        )
        redis_auth = secretsmanager.Secret(
            self,
            "RedisAuth",
            secret_name="quantum-dns/redis-auth",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True, password_length=32
            ),
        )

        # ── ElastiCache Redis ────────────────────────────────────────
        redis_subnet_group = elasticache.CfnSubnetGroup(
            self,
            "RedisSubnets",
            description="Redis subnet group",
            subnet_ids=[s.subnet_id for s in vpc.private_subnets],
        )

        redis_cluster = elasticache.CfnCacheCluster(
            self,
            "Redis",
            cache_node_type="cache.t4g.small",
            engine="redis",
            num_cache_nodes=1,
            vpc_security_group_ids=[sg_redis.security_group_id],
            cache_subnet_group_name=redis_subnet_group.ref,
            engine_version="7.0",
        )

        # ── S3 Bucket ───────────────────────────────────────────────
        audit_bucket = s3.Bucket(
            self,
            "AuditBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(30))],
        )

        # ── ECS Cluster + Service ────────────────────────────────────
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        image = ecr_assets.DockerImageAsset(
            self, "AppImage", directory="../"
        )

        task_def = ecs.FargateTaskDefinition(
            self, "TaskDef", cpu=2048, memory_limit_mib=4096
        )

        container = task_def.add_container(
            "App",
            image=ecs.ContainerImage.from_docker_image_asset(image),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="quantum-dns",
                log_retention=logs.RetentionDays.TWO_WEEKS,
            ),
            environment={
                "REDIS_HOST": redis_cluster.attr_redis_endpoint_address,
                "REDIS_PORT": redis_cluster.attr_redis_endpoint_port,
                "API_URL": "http://localhost:8000",
            },
            secrets={
                "IBM_QUANTUM_TOKEN": ecs.Secret.from_secrets_manager(ibm_token),
                "REDIS_PASSWORD": ecs.Secret.from_secrets_manager(redis_auth),
            },
        )

        container.add_port_mappings(
            ecs.PortMapping(container_port=8501),
            ecs.PortMapping(container_port=8000),
        )

        service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_def,
            desired_count=2,
            security_groups=[sg_app],
            assign_public_ip=False,
        )

        # ── ALB ──────────────────────────────────────────────────────
        alb = elbv2.ApplicationLoadBalancer(
            self, "ALB", vpc=vpc, internet_facing=True, security_group=sg_alb
        )

        # HTTPS or HTTP listener
        if certificate_arn:
            cert = acm.Certificate.from_certificate_arn(self, "Cert", certificate_arn)
            listener = alb.add_listener(
                "HTTPS", port=443, certificates=[cert]
            )
            # HTTP redirect to HTTPS
            alb.add_listener(
                "HTTPRedirect",
                port=80,
                action=elbv2.ListenerAction.redirect(
                    protocol="HTTPS", port="443", permanent=True
                ),
            )
        else:
            listener = alb.add_listener("HTTP", port=80)

        # API target group (port 8000)
        listener.add_targets(
            "API",
            port=8000,
            targets=[
                service.load_balancer_target(container_name="App", container_port=8000)
            ],
            health_check=elbv2.HealthCheck(path="/api/health", port="8000"),
            conditions=[elbv2.ListenerCondition.path_patterns(["/api/*"])],
            priority=1,
        )

        # Dashboard target group (port 8501, default)
        listener.add_targets(
            "Dashboard",
            port=8501,
            targets=[
                service.load_balancer_target(container_name="App", container_port=8501)
            ],
            health_check=elbv2.HealthCheck(path="/_stcore/health", port="8501"),
        )

        # ── Lambda: QRNG Generator ──────────────────────────────────
        qrng_lambda = lambda_.Function(
            self,
            "QRNGGenerator",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../src/lambda_handler"),
            memory_size=1024,
            timeout=Duration.minutes(5),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[sg_lambda],
            environment={
                "REDIS_HOST": redis_cluster.attr_redis_endpoint_address,
                "REDIS_PORT": redis_cluster.attr_redis_endpoint_port,
                "AUDIT_BUCKET": audit_bucket.bucket_name,
            },
        )

        ibm_token.grant_read(qrng_lambda)
        redis_auth.grant_read(qrng_lambda)
        audit_bucket.grant_write(qrng_lambda)

        # Schedule: every 5 minutes
        events.Rule(
            self,
            "QRNGSchedule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            targets=[targets.LambdaFunction(qrng_lambda)],
        )

        # ── CloudWatch Alarms ────────────────────────────────────────
        cloudwatch.Alarm(
            self,
            "PoolCritical",
            metric=cloudwatch.Metric(
                namespace="QuantumDNSShield",
                metric_name="qrng/PoolSize",
                statistic="Minimum",
                period=Duration.minutes(5),
            ),
            threshold=100,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            alarm_description="QRNG seed pool critically low",
        )

        # ── Outputs ──────────────────────────────────────────────────
        protocol = "https" if certificate_arn else "http"
        CfnOutput(
            self,
            "DashboardURL",
            value=f"{protocol}://{alb.load_balancer_dns_name}",
        )
        CfnOutput(
            self,
            "APIURL",
            value=f"{protocol}://{alb.load_balancer_dns_name}/api",
        )
        CfnOutput(
            self,
            "ALBDnsName",
            value=alb.load_balancer_dns_name,
            description="Use this for CNAME record in Namecheap",
        )
