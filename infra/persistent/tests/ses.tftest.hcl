mock_provider "aws" {}

variables {
  alert_email     = "alerts@example.com"
  mail_sender     = "sender@example.com"
  mail_recipients = ["sender@example.com", "friend@example.com"]
}

run "sender_and_each_recipient_are_verified_once" {
  command = apply
  assert {
    condition     = aws_ses_email_identity.sender.email == "sender@example.com"
    error_message = "The sender address must be a verified SES identity."
  }
  assert {
    condition     = keys(aws_ses_email_identity.recipient) == ["friend@example.com"]
    error_message = "Each recipient, except the sender, must be a verified SES identity."
  }
}

run "api_may_send_mail_only_as_the_sender" {
  command = apply
  assert {
    condition     = length([for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : s if contains(s.Action, "ses:SendEmail")]) == 1
    error_message = "The API task role must have exactly one statement for SES."
  }
  assert {
    condition     = [for s in jsondecode(aws_iam_role_policy.api_task.policy).Statement : s.Resource if contains(s.Action, "ses:SendEmail")][0] == aws_ses_email_identity.sender.arn
    error_message = "The API task role may send mail only as the sender identity."
  }
}
