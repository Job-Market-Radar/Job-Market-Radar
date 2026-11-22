resource "aws_security_group" "alb" {
  name        = "jmr-alb-sg"
  description = "Load balancer: HTTP from the internet"
  vpc_id      = var.vpc_id
  tags        = { Name = "jmr-alb-sg" }
}

resource "aws_security_group" "api" {
  name        = "jmr-api-sg"
  description = "API tasks: only from the load balancer"
  vpc_id      = var.vpc_id
  tags        = { Name = "jmr-api-sg" }
}

# Internet -> load balancer
resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from anywhere"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

# Load balancer -> API
resource "aws_vpc_security_group_egress_rule" "alb_to_api" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward to API tasks"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.api.id
}

resource "aws_vpc_security_group_ingress_rule" "api_from_alb" {
  security_group_id            = aws_security_group.api.id
  description                  = "From the load balancer only"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.alb.id
}

# API -> AWS services and Gemini (HTTPS)
resource "aws_vpc_security_group_egress_rule" "api_https" {
  security_group_id = aws_security_group.api.id
  description       = "HTTPS out: ECR, Secrets Manager, S3, Gemini"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# API -> database
resource "aws_vpc_security_group_egress_rule" "api_to_db" {
  security_group_id            = aws_security_group.api.id
  description                  = "Postgres"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = var.db_security_group_id
}

resource "aws_vpc_security_group_ingress_rule" "db_from_api" {
  security_group_id            = var.db_security_group_id
  description                  = "Postgres from API tasks only"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.api.id
}