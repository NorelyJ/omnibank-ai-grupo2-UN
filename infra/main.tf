terraform {
  required_version = ">= 1.7"
  backend "s3" {
    bucket = "omnibank-tfstate-381894834741"
    key    = "omnibank/terraform.tfstate"
    region = "us-east-1"
  }
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.8.1"
  name    = "omnibank-vpc"
  cidr    = "10.0.0.0/16"
  azs             = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = true
  tags = {
    Project     = "omnibank"
    Environment = var.environment
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.8.5"
  cluster_name    = "omnibank-eks"
  cluster_version = "1.29"
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  cluster_endpoint_public_access = true
  eks_managed_node_groups = {
    general = {
      instance_types = ["t3.medium"]
      min_size     = 2
      max_size     = 6
      desired_size = 2
    }
  }
  tags = { Project = "omnibank" }
}

resource "aws_ecr_repository" "agent" {
  name                 = "omnibank-agent"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = { Project = "omnibank" }
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "omnibank-redis-subnet"
  subnet_ids = module.vpc.private_subnets
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
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id        = "omnibank-redis"
  engine            = "redis"
  node_type         = "cache.t3.micro"
  num_cache_nodes   = 1
  engine_version    = "7.1"
  subnet_group_name = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]
  tags = { Project = "omnibank" }
}

resource "aws_secretsmanager_secret" "llm_key" {
  name                    = "omnibank/llm-api-key"
  recovery_window_in_days = 0
  tags = { Project = "omnibank" }
}

resource "aws_secretsmanager_secret_version" "llm_key" {
  secret_id     = aws_secretsmanager_secret.llm_key.id
  secret_string = jsonencode({ api_key = var.llm_api_key })
}
EOF