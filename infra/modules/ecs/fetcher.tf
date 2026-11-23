resource "aws_cloudwatch_log_group" "fetcher" {
  name              = "/ecs/jmr-fetcher"
  retention_in_days = 7
}

resource "aws_security_group" "fetcher" {
  name        = "jmr-fetcher-sg"
  description = "Fetcher task: outbound only"
  vpc_id      = var.vpc_id
  tags        = { Name = "jmr-fetcher-sg" }
}

resource "aws_vpc_security_group_egress_rule" "fetcher_https" {
  security_group_id = aws_security_group.fetcher.id
  description       = "HTTPS out: job sources, Gemini, AWS services"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "fetcher_to_db" {
  security_group_id            = aws_security_group.fetcher.id
  description                  = "Postgres"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = var.db_security_group_id
}

resource "aws_vpc_security_group_ingress_rule" "db_from_fetcher" {
  security_group_id            = var.db_security_group_id
  description                  = "Postgres from the fetcher task"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.fetcher.id
}

resource "aws_ecs_task_definition" "fetcher" {
  family                   = "jmr-fetcher"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "fetcher"
    image     = var.fetcher_image
    essential = true

    command = [
      "sh", "-c",
      "python fetch.py && python fetch_hn.py && python db.py && python extract_all.py && python embed.py"
    ]

    environment = [
      { name = "DB_HOST", value = var.db_host },
      { name = "DB_NAME", value = "jobradar" },
    ]

    secrets = [
      { name = "DB_USER", valueFrom = "${var.db_secret_arn}:username::" },
      { name = "DB_PASSWORD", valueFrom = "${var.db_secret_arn}:password::" },
      { name = "GEMINI_API_KEY", valueFrom = var.gemini_secret_arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.fetcher.name
        "awslogs-region"        = "eu-north-1"
        "awslogs-stream-prefix" = "fetcher"
      }
    }
  }])
}