mock_resource "aws_iam_role" {
  defaults = {
    arn = "arn:aws:iam::123456789012:role/mock"
  }
}

mock_resource "aws_sqs_queue" {
  defaults = {
    arn = "arn:aws:sqs:eu-west-1:123456789012:mock"
  }
}

mock_resource "aws_lambda_function" {
  defaults = {
    arn = "arn:aws:lambda:eu-west-1:123456789012:function:mock"
  }
}

mock_resource "aws_cloudwatch_event_rule" {
  defaults = {
    arn = "arn:aws:events:eu-west-1:123456789012:rule/mock"
  }
}

mock_data "aws_ec2_managed_prefix_list" {
  defaults = {
    id = "pl-00000000"
  }
}
