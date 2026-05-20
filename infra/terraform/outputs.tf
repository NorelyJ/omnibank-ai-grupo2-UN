output "eks_cluster_name"{
    value = module.eks_cluster_name
}

output "ecr_repository_url"{
    value = aws_ecr_repository.agent.repository_url
}

output "redis_endpoint"{
    value = aws_elasticache_cluster.redis.cache_nodes[0].address
}
