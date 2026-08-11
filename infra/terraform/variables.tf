variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment. Each maps to a separate AWS account so production execution credentials are unreachable from lower environments (docs/DEPLOYMENT.md)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the platform VPC"
  type        = string
  default     = "10.40.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class. Multi-AZ is enforced in prod: the audit trail must survive an AZ loss."
  type        = string
  default     = "db.t4g.medium"
}
