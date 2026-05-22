terraform {
  required_version = ">= 1.7"

  backend "s3" {
    bucket = "omnibank-tfstate-381894834741"
    key    = "omnibank/dev/terraform.tfstate"
    region = "us-east-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  common_tags = {
    Project     = "omnibank"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
