provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "project-hub"
      ManagedBy = "terraform"
      Layer     = "persistent"
    }
  }
}
