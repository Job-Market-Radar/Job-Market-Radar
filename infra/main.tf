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
  source            = "./modules/ecs"
  api_image         = "${module.registry.repository_urls["api"]}:${var.api_image_tag}"
  db_host           = module.data.db_endpoint
  db_secret_arn     = module.data.db_secret_arn
  gemini_secret_arn = module.data.gemini_secret_arn
  raw_bucket_arn    = module.data.raw_bucket_arn
}