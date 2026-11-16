mock_provider "aws" {
  source = "./tests/mocks"
}

variables {
  alert_email       = "alerts@example.com"
  image_preview_zip = "tests/fixtures/image-preview-lambda.zip"
}

run "storage_usage_reaches_only_the_database_and_the_vpc_endpoints" {
  command = apply
  assert {
    condition     = aws_security_group.storage_usage.name == "project-hub-storage-usage"
    error_message = "The Lambda security group must be named project-hub-storage-usage."
  }
  assert {
    condition     = aws_vpc_security_group_egress_rule.storage_usage_to_db.referenced_security_group_id == aws_security_group.db.id
    error_message = "The Lambda must reach PostgreSQL through the db security group."
  }
  assert {
    condition     = aws_vpc_security_group_egress_rule.storage_usage_to_db.from_port == 5432 && aws_vpc_security_group_egress_rule.storage_usage_to_db.to_port == 5432
    error_message = "The database egress rule must open port 5432 only."
  }
  assert {
    condition     = aws_vpc_security_group_egress_rule.storage_usage_https.cidr_ipv4 == aws_vpc.main.cidr_block
    error_message = "HTTPS egress must stay inside the VPC CIDR."
  }
  assert {
    condition     = aws_vpc_security_group_egress_rule.storage_usage_https.from_port == 443 && aws_vpc_security_group_egress_rule.storage_usage_https.to_port == 443
    error_message = "The VPC egress rule must open port 443 only."
  }
  assert {
    condition     = aws_vpc_security_group_egress_rule.storage_usage_s3.prefix_list_id == aws_vpc_endpoint.s3.prefix_list_id
    error_message = "S3 egress must target the gateway endpoint prefix list."
  }
  assert {
    condition     = aws_vpc_security_group_egress_rule.storage_usage_s3.from_port == 443 && aws_vpc_security_group_egress_rule.storage_usage_s3.to_port == 443
    error_message = "The S3 egress rule must open port 443 only."
  }
  assert {
    condition     = length(aws_security_group.storage_usage.ingress) == 0
    error_message = "Nothing may connect to the Lambda."
  }
}

run "database_accepts_the_storage_usage_lambda" {
  command = apply
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_storage_usage.referenced_security_group_id == aws_security_group.storage_usage.id
    error_message = "The database must accept the storage usage security group."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_storage_usage.from_port == 5432 && aws_vpc_security_group_ingress_rule.db_from_storage_usage.to_port == 5432
    error_message = "The database rule must open port 5432 only."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_storage_usage.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.db_from_storage_usage.cidr_ipv6 == null
    error_message = "The database rule must not admit any CIDR."
  }
}
