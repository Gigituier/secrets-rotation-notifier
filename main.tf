terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
    }
  }
}

# SNS Topic for notifications
resource "aws_sns_topic" "rotation_alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.rotation_alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# EventBridge rule to trigger Lambda daily
resource "aws_cloudwatch_event_rule" "daily_check" {
  name                = "${var.project_name}-daily-check"
  description         = "Trigger secrets rotation check daily"
  schedule_expression = var.lambda_schedule
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.daily_check.name
  target_id = "RotationNotifierLambda"
  arn       = aws_lambda_function.rotation_notifier.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotation_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_check.arn
}
