resource "aws_security_group" "alb" {
  #checkov:skip=CKV2_AWS_5:The load balancer in the ephemeral layer attaches this group
  name        = "project-hub-alb"
  description = "Public load balancer"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "app" {
  #checkov:skip=CKV2_AWS_5:The ECS service in the ephemeral layer attaches this group
  name        = "project-hub-app"
  description = "API tasks"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "db" {
  #checkov:skip=CKV2_AWS_5:The database in the ephemeral layer attaches this group
  name        = "project-hub-db"
  description = "PostgreSQL"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  #checkov:skip=CKV_AWS_260:Port 80 only redirects to HTTPS
  description       = "Public HTTP, redirected to HTTPS"
  security_group_id = aws_security_group.alb.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  description       = "Public HTTPS"
  security_group_id = aws_security_group.alb.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app" {
  description                  = "To the API tasks"
  security_group_id            = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  description                  = "From the load balancer"
  security_group_id            = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.alb.id
}

resource "aws_vpc_security_group_egress_rule" "app_https" {
  description       = "AWS APIs and ECR over the internet gateway"
  security_group_id = aws_security_group.app.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "app_to_db" {
  description                  = "To PostgreSQL"
  security_group_id            = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.db.id
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  description                  = "From the API tasks"
  security_group_id            = aws_security_group.db.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_egress_rule" "alb_to_web" {
  description                  = "To the web container of the app tasks"
  security_group_id            = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_ingress_rule" "app_web_from_alb" {
  description                  = "Web container, from the load balancer"
  security_group_id            = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  referenced_security_group_id = aws_security_group.alb.id
}
