locals {
  image     = "${data.aws_ecr_repository.api.repository_url}@${data.aws_ecr_image.api.image_digest}"
  web_image = "${data.aws_ecr_repository.web.repository_url}@${data.aws_ecr_image.web.image_digest}"

  log_configuration = {
    logDriver = "awslogs"
    options = {
      awslogs-group  = data.aws_cloudwatch_log_group.api.name
      awslogs-region = data.aws_region.current.region
    }
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "project-hub-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = data.aws_iam_role.ecs_execution.arn
  task_role_arn            = data.aws_iam_role.api_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  volume {
    name = "tmp"
  }

  container_definitions = jsonencode([
    {
      name      = "migrate"
      image     = local.image
      essential = false
      command   = ["python", "-m", "project_hub.db.migrate"]
      secrets = [
        { name = "APP_DATABASE_URL", valueFrom = "${local.ssm_arn_prefix}/database-url" },
      ]
      logConfiguration = merge(local.log_configuration, {
        options = merge(local.log_configuration.options, { awslogs-stream-prefix = "migrate" })
      })
    },
    {
      name      = "api"
      image     = local.image
      essential = true
      dependsOn = [{ containerName = "migrate", condition = "SUCCESS" }]
      portMappings = [
        { containerPort = 8000, protocol = "tcp" },
      ]
      readonlyRootFilesystem = true
      mountPoints = [
        { sourceVolume = "tmp", containerPath = "/tmp" },
      ]
      secrets = [
        { name = "APP_DATABASE_URL", valueFrom = "${local.ssm_arn_prefix}/database-url" },
        { name = "APP_JWT_SECRET", valueFrom = "${local.ssm_arn_prefix}/jwt-secret" },
        { name = "APP_DB_BACKEND", valueFrom = "${local.ssm_arn_prefix}/db-backend" },
        { name = "APP_S3_BUCKET", valueFrom = "${local.ssm_arn_prefix}/s3-bucket" },
        { name = "APP_MAIL_FROM", valueFrom = "${local.ssm_arn_prefix}/mail-from" },
      ]
      environment = [
        { name = "APP_S3_REGION", value = data.aws_region.current.region },
        { name = "APP_WEB_URL", value = "https://${aws_lb.api.dns_name}" },
        { name = "APP_PUBLIC_URL", value = "https://${aws_lb.api.dns_name}" },
        { name = "APP_MAIL_BACKEND", value = "ses" },
        { name = "APP_SES_REGION", value = data.aws_region.current.region },
      ]
      logConfiguration = merge(local.log_configuration, {
        options = merge(local.log_configuration.options, { awslogs-stream-prefix = "api" })
      })
    },
    {
      name      = "web"
      image     = local.web_image
      essential = true
      dependsOn = [{ containerName = "api", condition = "START" }]
      portMappings = [
        { containerPort = 8080, protocol = "tcp" },
      ]
      environment = [
        { name = "API_UPSTREAM", value = "127.0.0.1:8000" },
      ]
      logConfiguration = merge(local.log_configuration, {
        options = merge(local.log_configuration.options, { awslogs-stream-prefix = "web" })
      })
    },
  ])
}

resource "aws_ecs_service" "api" {
  #checkov:skip=CKV_AWS_333:The private subnets have no NAT gateway (billed); tasks reach ECR over the internet gateway and only the load balancer may connect in
  name                              = "project-hub-api"
  cluster                           = data.aws_ecs_cluster.main.arn
  task_definition                   = aws_ecs_task_definition.api.arn
  desired_count                     = 1
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 120
  wait_for_steady_state             = true

  network_configuration {
    subnets          = data.aws_subnets.public.ids
    security_groups  = [data.aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8080
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [
    aws_lb_listener.https,
    aws_ssm_parameter.database_url,
    aws_vpc_security_group_ingress_rule.ssm_endpoint_from_app,
  ]
}
