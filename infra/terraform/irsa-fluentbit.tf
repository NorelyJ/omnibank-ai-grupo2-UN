# Keyless CloudWatch access for the aws-for-fluent-bit DaemonSet via IRSA.
# `data.aws_caller_identity.current` is declared in irsa-bedrock.tf — reuse it.

module "fluentbit_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "5.39.0"

  role_name = "omnibank-fluentbit-cloudwatch"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-for-fluent-bit"]
    }
  }
  tags = local.common_tags
}

resource "aws_iam_role_policy" "fluentbit_cloudwatch" {
  name = "cloudwatch-logs"
  role = module.fluentbit_irsa.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams",
        "logs:PutRetentionPolicy",
      ]
      Resource = [
        "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/eks/omnibank:*",
        "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/eks/omnibank:log-stream:*",
      ]
    }]
  })
}
