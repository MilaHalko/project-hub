output "url" {
  value = local.public_url
}

output "alb_dns_name" {
  value = aws_lb.api.dns_name
}
