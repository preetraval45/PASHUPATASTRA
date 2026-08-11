environment       = "prod"
region            = "us-east-1"
db_instance_class = "db.t4g.medium"
# Multi-AZ, 30-day backups, deletion protection, and a final snapshot are all
# switched on by `environment == "prod"` in database.tf — not by a flag here, so
# they cannot be turned off by editing a variables file.
