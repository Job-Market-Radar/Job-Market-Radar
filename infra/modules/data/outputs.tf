output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "db_endpoint" {
  value = aws_db_instance.main.address
}

output "db_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "db_security_group_id" {
  value = aws_security_group.db.id
}

output "gemini_secret_arn" {
  value = aws_secretsmanager_secret.gemini_api_key.arn
}