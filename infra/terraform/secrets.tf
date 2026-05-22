resource "aws_secretsmanager_secret" "llm_key" {
  name                    = "omnibank/llm-api-key"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "llm_key" {
  secret_id     = aws_secretsmanager_secret.llm_key.id
  secret_string = jsonencode({ api_key = var.llm_api_key })
}
