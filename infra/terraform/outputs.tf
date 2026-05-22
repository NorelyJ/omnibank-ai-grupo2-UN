output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "ecr_repository_url" {
  description = "ECR repository URL (declared but unused — see ecr.tf and README)"
  value       = aws_ecr_repository.agent.repository_url
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Cognito app client ID (no secret, USER_PASSWORD_AUTH enabled)"
  value       = aws_cognito_user_pool_client.main.id
}

output "cognito_jwks_url" {
  description = "JWKS endpoint Kong's JWT plugin verifies tokens against"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
}

output "cognito_demo_users" {
  description = "Pre-provisioned demo users (username + custom:bank_customer_id). Password is var.cognito_demo_password (default Demo1234!)."
  value = {
    for k, u in local.demo_users : k => {
      email            = u.email
      bank_customer_id = u.bank_customer_id
    }
  }
}
