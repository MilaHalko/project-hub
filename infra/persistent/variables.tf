variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "availability_zones" {
  type    = list(string)
  default = ["eu-west-1a", "eu-west-1b"]
}

variable "github_repository" {
  type    = string
  default = "MilaHalko/project-hub"
}

variable "alert_email" {
  type        = string
  description = "Email address that receives AWS budget alerts"

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}
