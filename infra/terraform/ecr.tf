# ECR is declared but UNUSED in this project. CI publishes container images to
# GitHub Container Registry (ghcr.io) using the workflow's built-in GITHUB_TOKEN,
# which needs no AWS credentials. Pushing to ECR from CI would require wiring a
# GitHub-Actions -> AWS OIDC provider, which is not set up here.
#
# The resource is kept as a reference IaC pattern, so a future move to ECR is a
# one-line uncomment.

resource "aws_ecr_repository" "agent" {
  name                 = "omnibank-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}
