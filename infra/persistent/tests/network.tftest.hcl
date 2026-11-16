mock_provider "aws" {
  source = "./tests/mocks"
}

variables {
  alert_email       = "alerts@example.com"
  image_preview_zip = "tests/fixtures/image-preview-lambda.zip"
}

run "database_accepts_only_the_app" {
  command = apply
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_app.referenced_security_group_id == aws_security_group.app.id
    error_message = "The database must accept connections only from the app security group."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_app.from_port == 5432 && aws_vpc_security_group_ingress_rule.db_from_app.to_port == 5432
    error_message = "The database rule must open port 5432 only."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.db_from_app.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.db_from_app.cidr_ipv6 == null
    error_message = "The database rule must not admit any CIDR."
  }
}

run "app_accepts_only_the_load_balancer" {
  command = apply
  assert {
    condition     = aws_vpc_security_group_ingress_rule.app_from_alb.referenced_security_group_id == aws_security_group.alb.id
    error_message = "The API must accept connections only from the load balancer."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.app_from_alb.from_port == 8000 && aws_vpc_security_group_ingress_rule.app_from_alb.to_port == 8000
    error_message = "The API rule must open port 8000 only."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.app_from_alb.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.app_from_alb.cidr_ipv6 == null
    error_message = "The API rule must not admit any CIDR."
  }
}
