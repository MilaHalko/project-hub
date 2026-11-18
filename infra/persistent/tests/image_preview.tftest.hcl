mock_provider "aws" {
  source = "./tests/mocks"
}

variables {
  alert_email       = "alerts@example.com"
  mail_sender       = "sender@example.com"
  image_preview_zip = "tests/fixtures/image-preview-lambda.zip"
}

run "image_preview_cannot_write_documents" {
  command = apply
  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.image_preview.policy).Statement : [
        for a in flatten([s.Action]) : [
          for r in flatten([s.Resource]) : r == "${aws_s3_bucket.documents.arn}/projects/*/previews/*"
        ] if s.Effect == "Allow" && (contains(["s3:PutObject", "s3:DeleteObject"], a) || strcontains(a, "*"))
      ]
    ]))
    error_message = "The preview Lambda may write and delete only under projects/*/previews/, never under documents/."
  }
  assert {
    condition = anytrue(flatten([
      for s in jsondecode(aws_iam_role_policy.image_preview.policy).Statement : [
        for r in flatten([s.Resource]) : r == "${aws_s3_bucket.documents.arn}/projects/*/previews/*"
      ] if s.Effect == "Allow" && contains(flatten([s.Action]), "s3:PutObject")
    ]))
    error_message = "The preview Lambda must be able to store previews."
  }
}

run "missing_objects_read_as_missing_not_as_denied" {
  command = apply
  assert {
    condition = anytrue(flatten([
      for s in jsondecode(aws_iam_role_policy.image_preview.policy).Statement : [
        for r in flatten([s.Resource]) : r == aws_s3_bucket.documents.arn
      ] if s.Effect == "Allow" && contains(flatten([s.Action]), "s3:ListBucket") && try(s.Condition, null) == null
    ]))
    error_message = "The preview Lambda needs s3:ListBucket on the bucket, without a condition, or a document gone before it is read is AccessDenied instead of NoSuchKey."
  }
  assert {
    condition = anytrue(flatten([
      for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : [
        for r in flatten([s.Resource]) : r == aws_s3_bucket.documents.arn
      ] if s.Effect == "Allow" && contains(flatten([s.Action]), "s3:ListBucket") && try(s.Condition, null) == null
    ]))
    error_message = "The API needs s3:ListBucket on the bucket, without a condition, or a preview not made yet is AccessDenied (503) instead of NoSuchKey (404)."
  }
}

run "image_preview_rule_matches_only_documents" {
  command = apply
  assert {
    condition     = jsondecode(aws_cloudwatch_event_rule.image_preview.event_pattern).detail.object.key == [{ wildcard = "projects/*/documents/*" }]
    error_message = "The preview rule must match only projects/*/documents/* keys, so previews never start the Lambda again."
  }
  assert {
    condition     = jsondecode(aws_cloudwatch_event_rule.image_preview.event_pattern).detail.bucket.name == [aws_s3_bucket.documents.bucket]
    error_message = "The preview rule must match only the documents bucket."
  }
  assert {
    condition     = aws_cloudwatch_event_target.image_preview.arn == aws_lambda_function.image_preview.arn
    error_message = "The preview rule must invoke the preview Lambda."
  }
}
