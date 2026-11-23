resource "aws_cloudwatch_log_group" "ai" {
  name              = "/ecs/jmr-ai"
  retention_in_days = 7
}

# --- Security group: only from the load balancer ---
resource "aws_security_group" "ai" {
  name        = "jmr-ai-sg"
  description = "AI service tasks: only from the load balancer"
  vpc_id      = var.vpc_id
  tags        = { Name = "jmr-ai-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "ai_from_alb" {
  security_group_id            = aws_security_group.ai.id
  description                  = "From the load balancer only"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.alb.id
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ai" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward to AI service tasks"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.ai.id
}

resource "aws_vpc_security_group_egress_rule" "ai_https" {
  security_group_id = aws_security_group.ai.id
  description       = "HTTPS out: Gemini, AWS services"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "ai_to_db" {
  security_group_id            = aws_security_group.ai.id
  description                  = "Postgres"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = var.db_security_group_id
}

resource "aws_vpc_security_group_ingress_rule" "db_from_ai" {
  security_group_id            = var.db_security_group_id
  description                  = "Postgres from the AI service only"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.ai.id
}

# --- Load balancer: send AI paths to this service ---
resource "aws_lb_target_group" "ai" {
  name                 = "jmr-ai-tg"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = var.vpc_id
  deregistration_delay = 30

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener_rule" "ai" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ai.arn
  }

  condition {
    path_pattern {
      values = ["/jobs", "/jobs/*", "/stats/*", "/match-cv"]
    }
  }
}

# --- Task definition and service ---
resource "aws_ecs_task_definition" "ai" {
  family                   = "jmr-ai"
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
    name      = "ai"
    image     = var.ai_image
    essential = true

    portMappings = [{ containerPort = 8000, protocol = "tcp" }]

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
        "awslogs-group"         = aws_cloudwatch_log_group.ai.name
        "awslogs-region"        = "eu-north-1"
        "awslogs-stream-prefix" = "ai"
      }
    }
  }])
}

resource "aws_ecs_service" "ai" {
  name            = "jmr-ai"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.ai.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [aws_security_group.ai.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ai.arn
    container_name   = "ai"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 30

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener_rule.ai]
}