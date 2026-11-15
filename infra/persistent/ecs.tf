resource "aws_ecs_cluster" "main" {
  #checkov:skip=CKV_AWS_65:Container Insights is billed per metric; the design keeps it disabled
  name = "project-hub"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  #checkov:skip=CKV_AWS_158:AWS-managed encryption is free; a customer KMS key costs money
  #checkov:skip=CKV_AWS_338:Seven days of logs is a cost decision; one-year retention is billed
  name              = "/ecs/project-hub-api"
  retention_in_days = 7
}
