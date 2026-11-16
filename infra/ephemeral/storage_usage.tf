resource "aws_security_group" "ssm_endpoint" {
  name        = "project-hub-ssm-endpoint"
  description = "SSM interface endpoint"
  vpc_id      = data.aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "ssm_endpoint_from_storage_usage" {
  description                  = "From the storage usage Lambda"
  security_group_id            = aws_security_group.ssm_endpoint.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = data.aws_security_group.storage_usage.id
}

# Private DNS sends every SSM call in the VPC here, including the API tasks' secrets at start.
resource "aws_vpc_security_group_ingress_rule" "ssm_endpoint_from_app" {
  description                  = "From the API tasks"
  security_group_id            = aws_security_group.ssm_endpoint.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = data.aws_security_group.app.id
}

resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = data.aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = data.aws_subnets.private.ids
  security_group_ids  = [aws_security_group.ssm_endpoint.id]
  private_dns_enabled = true

  tags = {
    Name = "project-hub-ssm"
  }
}

resource "aws_sqs_queue" "storage_usage_dlq" {
  name                      = "project-hub-storage-usage-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "storage_usage" {
  name                       = "project-hub-storage-usage"
  visibility_timeout_seconds = 180
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.storage_usage_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_cloudwatch_event_rule" "storage_usage" {
  name = "project-hub-storage-usage"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created", "Object Deleted"]
    detail = {
      bucket = { name = [data.aws_ssm_parameter.s3_bucket.value] }
      object = { key = [{ wildcard = "projects/*/documents/*" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "storage_usage" {
  rule = aws_cloudwatch_event_rule.storage_usage.name
  arn  = aws_sqs_queue.storage_usage.arn
}

resource "aws_sqs_queue_policy" "storage_usage" {
  queue_url = aws_sqs_queue.storage_usage.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.storage_usage.arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.storage_usage.arn }
      }
    }]
  })
}

resource "aws_lambda_function" "storage_usage" {
  #checkov:skip=CKV_AWS_115:Reserved concurrency is refused on new accounts; the event source mapping caps concurrency instead
  #checkov:skip=CKV_AWS_116:A dead-letter queue is for asynchronous invocations; failures here return to the SQS queue and its DLQ
  #checkov:skip=CKV_AWS_173:Environment variables hold only a parameter name and a region, no secrets
  #checkov:skip=CKV_AWS_272:Code signing is postponed; the zip is built by the owner
  #checkov:skip=CKV_AWS_50:X-Ray tracing is billed; postponed by cost decision
  function_name    = "project-hub-storage-usage"
  role             = data.aws_iam_role.storage_usage.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "project_hub.storage_usage.handler.handler"
  memory_size      = 256
  timeout          = 30
  filename         = var.storage_usage_zip
  source_code_hash = filebase64sha256(var.storage_usage_zip)

  environment {
    variables = {
      APP_DATABASE_URL_PARAMETER = "/project-hub/database-url"
      APP_S3_REGION              = data.aws_region.current.region
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = data.aws_cloudwatch_log_group.storage_usage.name
  }

  vpc_config {
    subnet_ids         = data.aws_subnets.private.ids
    security_group_ids = [data.aws_security_group.storage_usage.id]
  }

  depends_on = [aws_vpc_endpoint.ssm, aws_ssm_parameter.database_url]
}

resource "aws_lambda_event_source_mapping" "storage_usage" {
  event_source_arn                   = aws_sqs_queue.storage_usage.arn
  function_name                      = aws_lambda_function.storage_usage.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 2
  function_response_types            = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = 2
  }
}
