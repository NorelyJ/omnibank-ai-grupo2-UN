resource "aws_cognito_user_pool" "main" {
  name = "omnibank-users"

  user_pool_tier = "ESSENTIALS"

  lambda_config {
    pre_token_generation_config {
      lambda_arn     = aws_lambda_function.pretoken.arn
      lambda_version = "V2_0"
    }
  }

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  # Stable per-customer identifier used by mock-core-banking. A Pre-Token-Generation
  # Lambda (V2_0) injects this into the access token as `bank_customer_id`; the agent
  # validates the access token (app/auth.py). See cognito-pretoken-lambda.tf.
  schema {
    name                = "bank_customer_id"
    attribute_data_type = "String"
    mutable             = false
    required            = false

    string_attribute_constraints {
      min_length = 1
      max_length = 50
    }
  }

  schema {
    name                     = "given_name"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 1
      max_length = 50
    }
  }

  tags = local.common_tags
}

resource "aws_cognito_user_pool_client" "main" {
  name         = "omnibank-app"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  id_token_validity      = 60
  access_token_validity  = 60
  refresh_token_validity = 30
  token_validity_units {
    id_token      = "minutes"
    access_token  = "minutes"
    refresh_token = "days"
  }

  read_attributes  = ["email", "email_verified", "given_name", "custom:bank_customer_id"]
  write_attributes = ["email", "given_name"]
}

locals {
  demo_users = {
    juan = {
      email            = "juan@omnibank.demo"
      given_name       = "Juan"
      bank_customer_id = "CUST-001"
    }
    maria = {
      email            = "maria@omnibank.demo"
      given_name       = "María"
      bank_customer_id = "CUST-002"
    }
    carlos = {
      email            = "carlos@omnibank.demo"
      given_name       = "Carlos"
      bank_customer_id = "CUST-003"
    }
  }
}

# Create the user with the temporary password and skip the welcome email.
resource "aws_cognito_user" "demo" {
  for_each = local.demo_users

  user_pool_id   = aws_cognito_user_pool.main.id
  username       = each.value.email
  message_action = "SUPPRESS"
  password       = var.cognito_demo_password

  attributes = {
    email                     = each.value.email
    email_verified            = "true"
    given_name                = each.value.given_name
    "custom:bank_customer_id" = each.value.bank_customer_id
  }
  lifecycle {
    ignore_changes = [attributes]
  }
}
