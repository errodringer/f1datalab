# OPTIONAL Terraform lab for the Moto/LocalStack AWS-side bucket.
# Run BEFORE docker compose up, or import the already-created bucket:
# terraform import aws_s3_bucket.f1_data_lake f1-data-lake
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "aws_endpoint_url" {
  default = "http://localhost:5000"
  type    = string
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3  = var.aws_endpoint_url
    sqs = var.aws_endpoint_url
  }
}

resource "aws_s3_bucket" "f1_data_lake" {
  bucket = "f1-data-lake"
}

resource "aws_sqs_queue" "raw_events" {
  name = "f1-raw-events"
}

output "s3_bucket" {
  value = aws_s3_bucket.f1_data_lake.bucket
}
output "sqs_queue_url" {
  value = aws_sqs_queue.raw_events.url
}
