# Terraform skeleton. Resources land in Phase 0.5 (data layer) and Phase 3
# (execution IAM) — see docs/ROADMAP.md. Kept minimal on purpose: untested
# infrastructure code is a liability, not a head start.

terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # State holds resource metadata and must not live in a laptop working copy.
  # Configure with -backend-config per environment.
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "pashupatastra"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
