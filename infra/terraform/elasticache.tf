resource "aws_elasticache_subnet_group" "redis" {
  name       = "omnibank-redis-subnet"
  subnet_ids = module.vpc.private_subnets
  tags       = local.common_tags
}

resource "aws_security_group" "redis" {
  name   = "omnibank-redis-sg"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  tags = local.common_tags
}

# No TLS / no AUTH for the MVP — documented production gap. The TLS-capable
# resource (aws_elasticache_replication_group) is harder to provision under
# AWS Academy's LabRole; revisit when moving to production.
resource "aws_elasticache_cluster" "redis" {
  cluster_id         = "omnibank-redis"
  engine             = "redis"
  node_type          = "cache.t3.micro"
  num_cache_nodes    = 1
  engine_version     = "7.1"
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]
  tags               = local.common_tags
}
