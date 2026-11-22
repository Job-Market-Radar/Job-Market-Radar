data "aws_caller_identity" "current" {}

# --- Raw-data bucket ---
resource "aws_s3_bucket" "raw" {
  bucket        = "jmr-raw-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Database ---
resource "aws_db_subnet_group" "main" {
  name       = "jmr-db-subnets"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "jmr-db-subnets" }
}

resource "aws_security_group" "db" {
  name        = "jmr-db-sg"
  description = "Postgres; ingress added on Day 4 from the API only"
  vpc_id      = var.vpc_id

  tags = { Name = "jmr-db-sg" }
}

resource "aws_db_instance" "main" {
  identifier     = "jmr-db"
  engine         = "postgres"
  engine_version = "17"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name                     = "jobradar"
  username                    = "jmr_admin"
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  tags = { Name = "jmr-db" }
}

# --- Secrets ---
resource "aws_secretsmanager_secret" "gemini_api_key" {
  name                    = "jmr/gemini-api-key"
  description             = "Gemini API key for extraction, embeddings and CV matching"
  recovery_window_in_days = 0
}