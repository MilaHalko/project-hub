mock_provider "aws" {}

variables {
  alert_email = "alerts@example.com"
  mail_sender = "sender@example.com"
}

run "deploy_role_trusts_only_main" {
  command = apply
  assert {
    condition     = length(jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement) == 1
    error_message = "The deploy role must have exactly one trust statement."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:MilaHalko/project-hub:ref:refs/heads/main"
    error_message = "Only the main branch of MilaHalko/project-hub may assume the deploy role."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    error_message = "The deploy role must require the STS audience."
  }
  assert {
    condition     = !contains(keys(jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Condition), "StringLike")
    error_message = "The deploy role must not match subjects with wildcards."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Principal.Federated == aws_iam_openid_connect_provider.github.arn
    error_message = "The deploy role must trust the GitHub OIDC provider."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Effect == "Allow"
    error_message = "The deploy role trust statement must be an Allow."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github_deploy.assume_role_policy).Statement[0].Action == "sts:AssumeRoleWithWebIdentity"
    error_message = "The deploy role must be assumable only with a GitHub web identity token."
  }
}
