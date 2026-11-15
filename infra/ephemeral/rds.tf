resource "aws_db_subnet_group" "main" {
  name       = "project-hub"
  subnet_ids = data.aws_subnets.private.ids
}

ephemeral "random_password" "db" {
  length  = 32
  special = false
}

locals {
  db_password_version = 1
}

resource "aws_db_instance" "main" {
  #checkov:skip=CKV_AWS_157:Multi-AZ doubles the cost; a single zone is enough for a demo
  #checkov:skip=CKV_AWS_293:Deletion protection would block the destroy after every checkpoint
  #checkov:skip=CKV_AWS_161:IAM database authentication is postponed; the app uses a password from SSM
  #checkov:skip=CKV_AWS_118:Enhanced monitoring is billed; postponed by cost decision
  #checkov:skip=CKV_AWS_353:Performance Insights is postponed by cost decision
  #checkov:skip=CKV_AWS_129:Log exports to CloudWatch are billed; postponed by cost decision
  #checkov:skip=CKV2_AWS_30:Query logging is postponed by cost decision
  #checkov:skip=CKV_AWS_354:Performance Insights is not enabled, so there is nothing to encrypt with a customer KMS key
  identifier        = "project-hub"
  engine            = "postgres"
  engine_version    = "18"
  instance_class    = "db.t4g.micro"
  allocated_storage = 20
  storage_type      = "gp3"

  db_name             = "project_hub"
  username            = "project_hub"
  password_wo         = ephemeral.random_password.db.result
  password_wo_version = local.db_password_version

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [data.aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false
  storage_encrypted      = true

  backup_retention_period    = 1
  skip_final_snapshot        = true
  deletion_protection        = false
  delete_automated_backups   = true
  apply_immediately          = true
  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true
}

resource "aws_ssm_parameter" "database_url" {
  #checkov:skip=CKV_AWS_337:The AWS-managed aws/ssm key is free; a customer KMS key costs money
  name             = "/project-hub/database-url"
  type             = "SecureString"
  value_wo         = "postgresql://project_hub:${ephemeral.random_password.db.result}@${aws_db_instance.main.address}:5432/project_hub?sslmode=require"
  value_wo_version = local.db_password_version
}
