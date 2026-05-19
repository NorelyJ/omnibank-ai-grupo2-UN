variable "aws_region"{
    description = "Region de AWS"
    default = "us-east-1"
}

variable "environment" {
    description = "ambiente de deployment"
    default = "dev"
}

variable "llm_api_key"{
    description = "API key del LLM (OpenAI o Anthropic)"
    type = string 
    sensitive = true
}