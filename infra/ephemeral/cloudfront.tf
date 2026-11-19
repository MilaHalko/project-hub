data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

resource "aws_cloudfront_distribution" "site" {
  #checkov:skip=CKV_AWS_68:A WAF is billed; postponed by cost decision
  #checkov:skip=CKV_AWS_86:Access logs need a billed S3 bucket; postponed by cost decision
  #checkov:skip=CKV_AWS_310:There is a single origin, so there is nothing to fail over to
  #checkov:skip=CKV_AWS_374:The site is public for visitors from any country
  #checkov:skip=CKV2_AWS_32:nginx in the web container already sets the security headers
  #checkov:skip=CKV2_AWS_42:The default *.cloudfront.net certificate is the point of this distribution; a custom one needs a domain name
  #checkov:skip=CKV_AWS_305:nginx serves the home page for the root path, so no default root object is needed
  #checkov:skip=CKV2_AWS_47:A WAF is billed; postponed by cost decision
  #checkov:skip=CKV_AWS_174:The default CloudFront certificate fixes the minimum TLS version, it cannot be set
  enabled         = true
  is_ipv6_enabled = true
  price_class     = "PriceClass_100"
  comment         = "project-hub"

  origin {
    origin_id   = "alb"
    domain_name = aws_lb.api.dns_name

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = random_password.origin_secret.result
    }
  }

  default_cache_behavior {
    target_origin_id         = "alb"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
