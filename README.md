# AWS Secrets Manager Rotation Notifier

Get email notifications 7 days before your AWS Secrets Manager secrets rotate.

## Problem
AWS Secrets Manager doesn't natively support pre-rotation notifications. This causes application teams to be caught off-guard when secrets rotate, leading to potential downtime.

## Solution
This project deploys a Lambda function that:
- Runs daily via EventBridge
- Checks all secrets across all AWS regions
- Sends email notification 7 days before rotation
- Includes secret name, region, and exact rotation date

## Prerequisites
- AWS Account with Secrets Manager secrets configured for rotation
- Terraform >= 1.0
- AWS CLI configured with appropriate credentials

## Quick Start

1. **Clone and navigate:**
```bash
cd secrets-rotation-notifier/terraform
```

2. **Configure:**
```bash
terraform init
```

3. **Deploy:**
```bash
terraform apply -var="notification_email=your-email@example.com"
```

4. **Confirm SNS subscription:**
Check your email and click the confirmation link from AWS SNS.

## Configuration

### Variables
- `notification_email` (required): Email address for notifications
- `threshold_days` (optional): Days before rotation to notify (default: 7)
- `lambda_schedule` (optional): Cron expression for checks (default: daily at 9 AM UTC)

### Example with custom threshold:
```bash
terraform apply \
  -var="notification_email=team@example.com" \
  -var="threshold_days=10"
```

## How It Works

1. EventBridge triggers Lambda daily
2. Lambda iterates through all AWS regions
3. For each region, lists all secrets with rotation enabled
4. Checks `NextRotationDate` for each secret
5. If rotation is exactly 7 days away, sends SNS notification
6. Email includes: secret name, ARN, region, rotation date

## Email Notification Example
```
Subject: Secret Rotation Alert: my-database-secret (7 days)

Secret Name: my-database-secret
Region: us-east-1
ARN: arn:aws:secretsmanager:us-east-1:123456789012:secret:my-database-secret-AbCdEf
Next Rotation: 2026-01-20 14:30:00 UTC
Days Until Rotation: 7

Action Required:
Prepare to restart/rebuild applications using this secret after rotation completes.
```

## Customization

### Monitor specific regions only:
Edit `lambda/rotation_notifier.py` and modify the `get_all_regions()` function to return your desired regions.

### Filter specific secrets:
Add tag-based filtering in the Lambda function to monitor only tagged secrets.

### Multiple notification channels:
Extend the SNS topic to include SMS, Slack webhooks, or other targets.

## Cost Estimate
- Lambda: ~$0.20/month (daily execution)
- SNS: $0.50/month (email notifications)
- **Total: < $1/month**

## Cleanup
```bash
terraform destroy -var="notification_email=your-email@example.com"
```

## License
MIT - Feel free to use and modify for your needs.
