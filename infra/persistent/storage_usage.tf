resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = {
    Name = "project-hub-s3"
  }
}

resource "aws_security_group" "storage_usage" {
  #checkov:skip=CKV2_AWS_5:The storage usage Lambda in the ephemeral layer attaches this group
  name        = "project-hub-storage-usage"
  description = "Storage usage Lambda"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_egress_rule" "storage_usage_to_db" {
  description                  = "To PostgreSQL"
  security_group_id            = aws_security_group.storage_usage.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.db.id
}

resource "aws_vpc_security_group_egress_rule" "storage_usage_https" {
  description       = "SSM interface endpoint"
  security_group_id = aws_security_group.storage_usage.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = aws_vpc.main.cidr_block
}

resource "aws_vpc_security_group_egress_rule" "storage_usage_s3" {
  description       = "S3 through the gateway endpoint"
  security_group_id = aws_security_group.storage_usage.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  prefix_list_id    = aws_vpc_endpoint.s3.prefix_list_id
}

resource "aws_vpc_security_group_ingress_rule" "db_from_storage_usage" {
  description                  = "From the storage usage Lambda"
  security_group_id            = aws_security_group.db.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.storage_usage.id
}

resource "aws_cloudwatch_log_group" "storage_usage" {
  #checkov:skip=CKV_AWS_158:AWS-managed encryption is free; a customer KMS key costs money
  #checkov:skip=CKV_AWS_338:Fourteen days of logs is a cost decision; one-year retention is billed
  name              = "/aws/lambda/project-hub-storage-usage"
  retention_in_days = 14
}

resource "aws_iam_role" "storage_usage" {
  name = "project-hub-storage-usage"
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

resource "aws_iam_role_policy_attachment" "storage_usage_vpc" {
  role       = aws_iam_role.storage_usage.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "storage_usage" {
  name = "project-hub-storage-usage"
  role = aws_iam_role.storage_usage.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.documents.arn
        Condition = { StringLike = { "s3:prefix" = "projects/*" } }
      },
      {
        Effect   = "Allow"
        Action   = "ssm:GetParameter"
        Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/project-hub/database-url"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = "arn:aws:sqs:${var.region}:${data.aws_caller_identity.current.account_id}:project-hub-storage-usage"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.storage_usage.arn}:*"
      },
    ]
  })
}
