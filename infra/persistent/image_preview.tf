resource "aws_cloudwatch_log_group" "image_preview" {
  #checkov:skip=CKV_AWS_158:AWS-managed encryption is free; a customer KMS key costs money
  #checkov:skip=CKV_AWS_338:Fourteen days of logs is a cost decision; one-year retention is billed
  name              = "/aws/lambda/project-hub-image-preview"
  retention_in_days = 14
}

resource "aws_sqs_queue" "image_preview_dlq" {
  name                      = "project-hub-image-preview-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_iam_role" "image_preview" {
  name = "project-hub-image-preview"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "image_preview" {
  name = "project-hub-image-preview"
  role = aws_iam_role.image_preview.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.documents.arn}/projects/*/documents/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.documents.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.documents.arn}/projects/*/previews/*"
      },
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.image_preview_dlq.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.image_preview.arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "image_preview" {
  #checkov:skip=CKV_AWS_115:Reserved concurrency is refused on new accounts; the function only reads and writes S3
  #checkov:skip=CKV_AWS_117:The function needs no database or private resource; outside the VPC it reaches S3 without a NAT gateway
  #checkov:skip=CKV_AWS_173:Environment variables hold only a region, no secrets
  #checkov:skip=CKV_AWS_272:Code signing is postponed; the zip is built by the owner
  #checkov:skip=CKV_AWS_50:X-Ray tracing is billed; postponed by cost decision
  function_name    = "project-hub-image-preview"
  role             = aws_iam_role.image_preview.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "project_hub.image_preview.handler.handler"
  memory_size      = 512
  timeout          = 30
  filename         = var.image_preview_zip
  source_code_hash = filebase64sha256(var.image_preview_zip)

  environment {
    variables = {
      APP_S3_REGION = var.region
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.image_preview_dlq.arn
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.image_preview.name
  }

  depends_on = [aws_iam_role_policy.image_preview]
}

resource "aws_lambda_function_event_invoke_config" "image_preview" {
  function_name                = aws_lambda_function.image_preview.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 3600
}

resource "aws_cloudwatch_event_rule" "image_preview" {
  name = "project-hub-image-preview"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created", "Object Deleted"]
    detail = {
      bucket = { name = [aws_s3_bucket.documents.bucket] }
      object = { key = [{ wildcard = "projects/*/documents/*" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "image_preview" {
  rule = aws_cloudwatch_event_rule.image_preview.name
  arn  = aws_lambda_function.image_preview.arn

  retry_policy {
    maximum_retry_attempts       = 2
    maximum_event_age_in_seconds = 3600
  }

  dead_letter_config {
    arn = aws_sqs_queue.image_preview_dlq.arn
  }
}

resource "aws_sqs_queue_policy" "image_preview_dlq" {
  queue_url = aws_sqs_queue.image_preview_dlq.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.image_preview_dlq.arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.image_preview.arn }
      }
    }]
  })
}

resource "aws_lambda_permission" "image_preview_events" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_preview.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.image_preview.arn
}
