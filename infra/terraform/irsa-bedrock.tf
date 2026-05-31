# Keyless Bedrock access for the nlp-agent pod via IRSA.
# The pod's ServiceAccount (default:nlp-agent) assumes this role; the role may
# invoke the Claude Haiku model (and its cross-region inference profile).

data "aws_caller_identity" "current" {}

module "nlp_agent_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "5.39.0"

  role_name = "omnibank-nlp-agent-bedrock"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["default:nlp-agent"]
    }
  }

  tags = local.common_tags
}

resource "aws_iam_role_policy" "nlp_agent_bedrock" {
  name = "bedrock-invoke"
  role = module.nlp_agent_irsa.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
      ]
      # Cross-region inference profile + the underlying foundation model in any
      # region the profile may route to.
      Resource = [
        "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-3-5-haiku-*",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-haiku-*",
      ]
    }]
  })
}
