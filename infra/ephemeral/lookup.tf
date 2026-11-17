data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  ssm_arn_prefix = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter/project-hub"
}

data "aws_vpc" "main" {
  tags = {
    Name = "project-hub"
  }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }

  tags = {
    Tier = "public"
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }

  tags = {
    Tier = "private"
  }
}

data "aws_security_group" "alb" {
  name   = "project-hub-alb"
  vpc_id = data.aws_vpc.main.id
}

data "aws_security_group" "app" {
  name   = "project-hub-app"
  vpc_id = data.aws_vpc.main.id
}

data "aws_security_group" "db" {
  name   = "project-hub-db"
  vpc_id = data.aws_vpc.main.id
}

data "aws_ecs_cluster" "main" {
  cluster_name = "project-hub"
}

data "aws_iam_role" "ecs_execution" {
  name = "project-hub-ecs-execution"
}

data "aws_iam_role" "api_task" {
  name = "project-hub-api-task"
}

data "aws_ecr_repository" "api" {
  name = "project-hub-api"
}

data "aws_ecr_image" "api" {
  repository_name = "project-hub-api"
  most_recent     = true
}

data "aws_cloudwatch_log_group" "api" {
  name = "/ecs/project-hub-api"
}

data "aws_ecr_repository" "web" {
  name = "project-hub-web"
}

data "aws_ecr_image" "web" {
  repository_name = "project-hub-web"
  most_recent     = true
}
