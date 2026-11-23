output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.network.private_subnet_ids
}

output "raw_bucket" {
  value = module.data.raw_bucket
}

output "db_endpoint" {
  value = module.data.db_endpoint
}

output "db_secret_arn" {
  value = module.data.db_secret_arn
}

output "ecr_repository_urls" {
  value = module.registry.repository_urls
}

output "app_url" {
  value = "http://${module.ecs.alb_dns_name}"
}

output "fetcher_security_group_id" {
  value = module.ecs.fetcher_security_group_id
}