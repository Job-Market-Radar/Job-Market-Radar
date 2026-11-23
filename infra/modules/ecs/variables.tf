variable "api_image" {
  type = string
}

variable "db_host" {
  type = string
}

variable "db_secret_arn" {
  type = string
}

variable "gemini_secret_arn" {
  type = string
}

variable "raw_bucket_arn" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "db_security_group_id" {
  type = string
}

variable "fetcher_image" {
  type = string
}

variable "ai_image" {
  type = string
}