variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "availability_zones" {
  type    = list(string)
  default = ["eu-west-1a", "eu-west-1b"]
}

variable "github_oidc_subject_prefix" {
  type        = string
  default     = "repo:MilaHalko@73230089/project-hub@1453204523"
  description = "Subject prefix GitHub puts in this repository's OIDC tokens. The repository uses immutable subjects (owner and repo ids), so the plain owner/name form never matches: gh api repos/MilaHalko/project-hub/actions/oidc/customization/sub"
}

variable "alert_email" {
  type        = string
  description = "Email address that receives AWS budget alerts"

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}

variable "mail_sender" {
  type        = string
  description = "Address the share email is sent from; SES verifies it (a personal address, never a corporate one)"

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.mail_sender))
    error_message = "mail_sender must be a valid email address."
  }
}

variable "mail_recipients" {
  type        = list(string)
  default     = []
  description = "Addresses the demo may share to; the SES sandbox delivers only to verified addresses"

  validation {
    condition     = alltrue([for address in var.mail_recipients : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", address))])
    error_message = "Every mail_recipients entry must be a valid email address."
  }
}
