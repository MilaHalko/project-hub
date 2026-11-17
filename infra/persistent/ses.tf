resource "aws_ses_email_identity" "sender" {
  email = var.mail_sender
}

resource "aws_ses_email_identity" "recipient" {
  for_each = toset([for address in var.mail_recipients : address if address != var.mail_sender])
  email    = each.value
}
