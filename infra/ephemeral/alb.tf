resource "aws_lb" "api" {
  #checkov:skip=CKV_AWS_91:Access logs need a billed S3 bucket; postponed by cost decision
  #checkov:skip=CKV_AWS_150:Deletion protection would block the destroy after every checkpoint
  #checkov:skip=CKV2_AWS_28:A WAF is billed; postponed by cost decision
  #checkov:skip=CKV2_AWS_20:CloudFront redirects viewers from HTTP to HTTPS; port 80 here is only the CloudFront hop
  name                       = "project-hub"
  load_balancer_type         = "application"
  internal                   = false
  subnets                    = data.aws_subnets.public.ids
  security_groups            = [data.aws_security_group.alb.id]
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "web" {
  #checkov:skip=CKV_AWS_378:The web container has no certificate; the hop stays inside the VPC
  name                 = "project-hub-web"
  port                 = 8080
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = data.aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path    = "/api/health"
    matcher = "200"
  }
}

resource "random_password" "origin_secret" {
  length  = 40
  special = false
}

resource "aws_lb_listener" "http" {
  #checkov:skip=CKV_AWS_2:CloudFront cannot verify a self-signed certificate; port 80 admits only the CloudFront prefix list and requests carrying the secret header
  #checkov:skip=CKV_AWS_103:The listener speaks plain HTTP, so no TLS policy applies
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }
}

resource "aws_lb_listener_rule" "from_cloudfront" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 1

  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [random_password.origin_secret.result]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}
