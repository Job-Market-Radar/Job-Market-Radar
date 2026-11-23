module "network" {
  source = "./modules/network"
}

module "data" {
  source             = "./modules/data"
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
}

module "registry" {
  source = "./modules/registry"
}

module "ecs" {
  source               = "./modules/ecs"
  api_image            = "${module.registry.repository_urls["api"]}:${var.api_image_tag}"
  db_host              = module.data.db_endpoint
  db_secret_arn        = module.data.db_secret_arn
  gemini_secret_arn    = module.data.gemini_secret_arn
  raw_bucket_arn       = module.data.raw_bucket_arn
  vpc_id               = module.network.vpc_id
  public_subnet_ids    = module.network.public_subnet_ids
  db_security_group_id = module.data.db_security_group_id
  fetcher_image        = "${module.registry.repository_urls["fetcher"]}:${var.ai_image_tag}"
  ai_image             = "${module.registry.repository_urls["ai"]}:${var.ai_image_tag}"
}

module "cicd" {
  source       = "./modules/cicd"
  github_repo  = "Job-Market-Radar@357161711/Job-Market-Radar@1459352965"
  state_bucket = "jmr-tfstate-885069197789"
}