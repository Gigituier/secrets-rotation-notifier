variable "notification_email" {
  description = "Email address to receive rotation notifications"
  type        = string
}

variable "threshold_days" {
  description = "Number of days before rotation to send notification"
  type        = number
  default     = 7
}

variable "lambda_schedule" {
  description = "Cron expression for Lambda execution (default: daily at 9 AM UTC)"
  type        = string
  default     = "cron(0 9 * * ? *)"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "secrets-rotation-notifier"
}
