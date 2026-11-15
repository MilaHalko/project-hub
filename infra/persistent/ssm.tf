ephemeral "random_password" "jwt_secret" {
  length  = 48
  special = false
}

resource "aws_ssm_parameter" "jwt_secret" {
  #checkov:skip=CKV_AWS_337:The AWS-managed aws/ssm key is free; a customer KMS key costs money
  name             = "/project-hub/jwt-secret"
  type             = "SecureString"
  value_wo         = ephemeral.random_password.jwt_secret.result
  value_wo_version = 1
}

resource "aws_ssm_parameter" "db_backend" {
  #checkov:skip=CKV2_AWS_34:Holds a non-secret setting, not a secret; the API reads it as a plain String
  name  = "/project-hub/db-backend"
  type  = "String"
  value = "orm"

  lifecycle {
    # The value is flipped in the console during the demo; apply must not revert it.
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "s3_bucket" {
  #checkov:skip=CKV2_AWS_34:Holds a non-secret setting, not a secret; the bucket name is public configuration
  name  = "/project-hub/s3-bucket"
  type  = "String"
  value = aws_s3_bucket.documents.bucket
}
