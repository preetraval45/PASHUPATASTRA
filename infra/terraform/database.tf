# RDS PostgreSQL — the durable home of incidents, verdicts, and the audit trail.
#
# Multi-AZ in production is not a performance choice: the audit trail surviving
# an AZ loss is a correctness requirement (Platform ADR).

data "aws_availability_zones" "available" {
  state = "available"
}

# --------------------------------------------------------------- networking --

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "pashupatastra-${var.environment}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = { Name = "pashupatastra-${var.environment}-private-${count.index}" }
}

resource "aws_db_subnet_group" "main" {
  name       = "pashupatastra-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "database" {
  name        = "pashupatastra-${var.environment}-db"
  description = "Postgres access from the platform only"
  vpc_id      = aws_vpc.main.id

  # No ingress rule here on purpose. Access is granted by referencing this group
  # from the application security group, so the database is never open to a CIDR
  # range — including, especially, 0.0.0.0/0.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ----------------------------------------------------------------- password --

# Generated and stored in Secrets Manager; never written to a variable file, an
# environment file, or a chat window (SECURITY.md, T9).
resource "random_password" "database" {
  length  = 32
  special = true
  # RDS rejects these in a master password.
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "database" {
  name                    = "pashupatastra/${var.environment}/database"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id
  secret_string = jsonencode({
    username = "pashupatastra"
    password = random_password.database.result
    dbname   = "pashupatastra"
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    url      = "postgresql://pashupatastra:${urlencode(random_password.database.result)}@${aws_db_instance.main.endpoint}/pashupatastra"
  })
}

# ---------------------------------------------------------------- instance --

resource "aws_db_instance" "main" {
  identifier     = "pashupatastra-${var.environment}"
  engine         = "postgres"
  engine_version = "16.14"
  instance_class = var.db_instance_class

  db_name  = "pashupatastra"
  username = "pashupatastra"
  password = random_password.database.result

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false

  multi_az = var.environment == "prod"

  backup_retention_period = var.environment == "prod" ? 30 : 7
  backup_window           = "07:00-08:00"
  maintenance_window      = "Mon:08:30-Mon:09:30"

  # Audit data must not vanish with the instance.
  deletion_protection       = var.environment == "prod"
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "pashupatastra-prod-final" : null

  performance_insights_enabled    = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  # The platform reasons about database saturation, so it needs headroom to
  # observe rather than a pool sized to the instance default.
  parameter_group_name = aws_db_parameter_group.main.name

  tags = { Name = "pashupatastra-${var.environment}" }
}

resource "aws_db_parameter_group" "main" {
  name   = "pashupatastra-${var.environment}"
  family = "postgres16"

  parameter {
    name         = "log_min_duration_statement"
    value        = "1000"
    apply_method = "immediate"
  }

  parameter {
    name         = "log_connections"
    value        = "1"
    apply_method = "immediate"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ----------------------------------------------------------------- outputs --

output "database_endpoint" {
  description = "RDS endpoint. The password lives in Secrets Manager, never here."
  value       = aws_db_instance.main.endpoint
}

output "database_secret_arn" {
  description = "Secrets Manager ARN holding the connection details"
  value       = aws_secretsmanager_secret.database.arn
}
