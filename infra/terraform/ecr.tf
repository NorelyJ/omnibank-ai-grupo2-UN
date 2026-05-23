# ECR is declared but UNUSED in this project. We publish container images to
# GitHub Container Registry (ghcr.io) instead — see README "Locked
# architectural compromises" for the rationale: AWS Academy's LabRole cannot
# create the OIDC provider that GitHub Actions would need to push to ECR
# without rotating session credentials.
#
# The resource is kept here as a reference of the IaC pattern and so that a
# future move back to ECR (post-Academy) is a one-line uncomment.

resource "aws_ecr_repository" "agent" {
  name                 = "omnibank-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}
