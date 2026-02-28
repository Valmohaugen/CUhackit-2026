"""CDK stack for Quantum DNS Shield.

Deploys: VPC, ALB (HTTP), CloudFront (HTTPS + custom domain), ECS Fargate,
ElastiCache Redis, S3 audit bucket, Secrets Manager, CloudWatch dashboard,
SNS alerting.

QRNG seed generation runs as a background task inside the FastAPI container
(no separate Lambda needed).
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
    aws_logs as logs,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_cloudwatch_actions as cw_actions,
)
from aws_cdk import aws_cloudfront as cloudfront, aws_cloudfront_origins as origins
from constructs import Construct


class QuantumDNSStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Optional HTTPS custom domain: pass -c certificate_arn=arn:aws:acm:...
        certificate_arn = self.node.try_get_context("certificate_arn")

        # ── VPC ──────────────────────────────────────────────────────
        vpc = ec2.Vpc(
            self,
            "VPC",
            max_azs=2,
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

        # ALB inbound (HTTP only — CloudFront terminates TLS)
        sg_alb.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")

        # App from ALB
        sg_app.add_ingress_rule(sg_alb, ec2.Port.tcp(8501), "Streamlit from ALB")
        sg_app.add_ingress_rule(sg_alb, ec2.Port.tcp(8000), "FastAPI from ALB")

        # Redis from app
        sg_redis.add_ingress_rule(sg_app, ec2.Port.tcp(6379), "Redis from ECS")

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
        openai_key = secretsmanager.Secret(
            self, "OpenAIKey", secret_name="quantum-dns/openai-key"
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
            cache_node_type="cache.t4g.medium",
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
            self,
            "AppImage",
            directory="../",
            exclude=[
                "cdk.out",
                "infra/cdk.out",
                ".git",
                ".gitignore",
                "tests",
                "__pycache__",
                "*.pyc",
                ".env",
                ".claude",
            ],
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
                "AUDIT_BUCKET": audit_bucket.bucket_name,
            },
            secrets={
                "IBM_QUANTUM_TOKEN": ecs.Secret.from_secrets_manager(ibm_token),
                "REDIS_PASSWORD": ecs.Secret.from_secrets_manager(redis_auth),
                "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(openai_key),
            },
        )

        # Grant ECS task write access to audit bucket
        audit_bucket.grant_write(task_def.task_role)

        container.add_port_mappings(
            ecs.PortMapping(container_port=8501),
            ecs.PortMapping(container_port=8000),
        )

        service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_def,
            desired_count=1,
            security_groups=[sg_app],
            assign_public_ip=False,
        )

        # ── ECS Auto-Scaling ───────────────────────────────────────
        scaling = service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2,
        )
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=60,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(30),
        )

        # ── ALB (HTTP only — CloudFront handles HTTPS) ──────────────
        alb = elbv2.ApplicationLoadBalancer(
            self, "ALB", vpc=vpc, internet_facing=True, security_group=sg_alb
        )

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
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[
                service.load_balancer_target(container_name="App", container_port=8501)
            ],
            health_check=elbv2.HealthCheck(path="/_stcore/health", port="8501"),
            stickiness_cookie_duration=Duration.hours(1),
        )

        # ── SNS Alerting ────────────────────────────────────────────
        alert_topic = sns.Topic(
            self,
            "AlertTopic",
            display_name="Quantum DNS Shield Alerts",
        )

        # ── CloudWatch Alarms ────────────────────────────────────────
        pool_alarm = cloudwatch.Alarm(
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
        pool_alarm.add_alarm_action(cw_actions.SnsAction(alert_topic))

        # ── CloudWatch Dashboard ────────────────────────────────────
        dashboard = cloudwatch.Dashboard(
            self, "Dashboard", dashboard_name="QuantumDNSShield"
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="QRNG Pool Size",
                left=[cloudwatch.Metric(
                    namespace="QuantumDNSShield",
                    metric_name="qrng/PoolSize",
                    statistic="Average",
                    period=Duration.minutes(5),
                )],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="ALB Request Count",
                left=[cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="RequestCount",
                    dimensions_map={"LoadBalancer": alb.load_balancer_full_name},
                    statistic="Sum",
                    period=Duration.minutes(1),
                )],
                width=12,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ECS CPU Utilization",
                left=[service.metric_cpu_utilization(period=Duration.minutes(1))],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="ECS Task Count",
                left=[service.metric("RunningTaskCount",
                    statistic="Average",
                    period=Duration.minutes(1),
                )],
                width=12,
            ),
        )

        # ── CloudFront CDN (HTTPS termination) ──────────────────────
        alb_origin = origins.LoadBalancerV2Origin(
            alb, protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY
        )

        cf_kwargs: dict = dict(
            default_behavior=cloudfront.BehaviorOptions(
                origin=alb_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            ),
        )

        if certificate_arn:
            cert = acm.Certificate.from_certificate_arn(self, "Cert", certificate_arn)
            cf_kwargs["domain_names"] = ["qdns.valmohaugen.com"]
            cf_kwargs["certificate"] = cert

        cdn = cloudfront.Distribution(self, "CDN", **cf_kwargs)

        # ── Outputs ──────────────────────────────────────────────────
        CfnOutput(
            self,
            "DashboardURL",
            value=f"https://{cdn.distribution_domain_name}",
        )
        CfnOutput(
            self,
            "APIURL",
            value=f"https://{cdn.distribution_domain_name}/api",
        )
        CfnOutput(
            self,
            "ALBDnsName",
            value=alb.load_balancer_dns_name,
            description="Internal ALB (HTTP only)",
        )
        CfnOutput(
            self,
            "CloudFrontDomain",
            value=cdn.distribution_domain_name,
            description="Add CNAME: qdns.valmohaugen.com -> this value",
        )
