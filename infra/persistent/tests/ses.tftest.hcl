mock_provider "aws" {
  source = "./tests/mocks"
}

variables {
  alert_email       = "alerts@example.com"
  mail_sender       = "sender@example.com"
  image_preview_zip = "tests/fixtures/image-preview-lambda.zip"
}

run "sender_is_a_verified_identity" {
  command = apply
  assert {
    condition     = aws_ses_email_identity.sender.email == "sender@example.com"
    error_message = "The sender address must be a verified SES identity."
  }
}

run "api_sends_mail_only_from_the_sender_address" {
  command = apply
  assert {
    condition     = length([for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : s if contains(s.Action, "ses:SendEmail")]) == 1
    error_message = "The API task role must have exactly one statement for sending mail."
  }
  assert {
    condition     = [for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : s.Condition.StringEquals["ses:FromAddress"] if contains(s.Action, "ses:SendEmail")][0] == "sender@example.com"
    error_message = "The API task role may send mail only from the sender address."
  }
}

run "api_may_only_look_up_and_create_ses_identities" {
  command = apply
  assert {
    condition     = contains([for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : s.Action], ["ses:GetEmailIdentity", "ses:CreateEmailIdentity"])
    error_message = "The API task role may only look up and create SES identities, not delete or change them."
  }
}
