data "archive_file" "pretoken" {
  type        = "zip"
  source_dir  = "${path.module}/lambda/pretoken"
  output_path = "${path.module}/lambda/pretoken.zip"
}

resource "aws_iam_role" "pretoken" {
  name = "omnibank-cognito-pretoken"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "pretoken_logs" {
  role       = aws_iam_role.pretoken.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "pretoken" {
  function_name    = "omnibank-cognito-pretoken"
  role             = aws_iam_role.pretoken.arn
  runtime          = "python3.12"
  handler          = "index.handler"
  filename         = data.archive_file.pretoken.output_path
  source_code_hash = data.archive_file.pretoken.output_base64sha256
  timeout          = 5
  tags             = local.common_tags
}

resource "aws_lambda_permission" "cognito_invoke" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pretoken.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.main.arn
}
