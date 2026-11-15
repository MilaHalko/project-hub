resource "aws_lb" "api" {
  #checkov:skip=CKV_AWS_91:Access logs need a billed S3 bucket; postponed by cost decision
  #checkov:skip=CKV_AWS_150:Deletion protection would block the destroy after every checkpoint
  #checkov:skip=CKV2_AWS_28:A WAF is billed; postponed by cost decision
  name                       = "project-hub"
  load_balancer_type         = "application"
  internal                   = false
  subnets                    = data.aws_subnets.public.ids
  security_groups            = [data.aws_security_group.alb.id]
  drop_invalid_header_fields = true
}

resource "tls_private_key" "alb" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "alb" {
  private_key_pem       = tls_private_key.alb.private_key_pem
  dns_names             = [aws_lb.api.dns_name]
  validity_period_hours = 720
  allowed_uses          = ["key_encipherment", "digital_signature", "server_auth"]

  subject {
    common_name = aws_lb.api.dns_name
  }
}

resource "aws_acm_certificate" "alb" {
  private_key      = tls_private_key.alb.private_key_pem
  certificate_body = tls_self_signed_cert.alb.cert_pem

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_target_group" "api" {
  name                 = "project-hub-api"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = data.aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      protocol    = "HTTPS"
      port        = "443"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.alb.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
