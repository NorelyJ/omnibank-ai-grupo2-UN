variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (dev / prod)"
  type        = string
  default     = "dev"
}

variable "llm_api_key" {
  description = "OpenAI API key (stored in Secrets Manager, never in plaintext)"
  type        = string
  sensitive   = true
}

variable "cognito_demo_password" {
  description = "Password set for the three pre-provisioned demo users (Juan/María/Carlos)"
  type        = string
  sensitive   = true
  default     = "Demo1234!"
}
