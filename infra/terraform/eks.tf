module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.8.5"

  cluster_name    = "omnibank-eks"
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    general = {
      instance_types = ["t3.micro"]
      min_size       = 2
      max_size       = 6
      desired_size   = 3
    }
  }

  tags = local.common_tags
}
