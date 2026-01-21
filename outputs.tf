output "sns_topic_arn" {
  description = "ARN of the SNS topic for notifications"
  value       = aws_sns_topic.rotation_alerts.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.rotation_notifier.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.rotation_notifier.arn
}

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_check.name
}

output "next_steps" {
  description = "Next steps after deployment"
  value       = <<-EOT
    Deployment complete! Next steps:
    
    1. Check your email (${var.notification_email}) for SNS subscription confirmation
    2. Click the confirmation link in the email
    3. Test the function manually:
       aws lambda invoke --function-name ${aws_lambda_function.rotation_notifier.function_name} response.json
    4. Check CloudWatch Logs for execution details
    
    The function will run automatically at: ${var.lambda_schedule}
  EOT
}
