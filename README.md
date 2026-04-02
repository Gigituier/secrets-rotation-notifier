# AWS Secrets Manager Rotation Notifier

Get proactive email alerts when AWS Secrets Manager secrets are about to rotate — and when rotation silently fails.

## Problem

AWS Secrets Manager doesn't natively notify you before a secret rotates or when rotation fails. Teams find out through application outages — expired credentials, failed connections, service disruptions.

## Solution

A Lambda function that runs daily via EventBridge, scans all AWS regions, and sends SNS email alerts for two scenarios:

1. **Upcoming rotation** — 7 days before a secret rotates, giving teams time to prepare
2. **Failed rotation** — detects secrets that never rotated or stopped rotating, before it becomes an outage

### Built-in safeguards

- **Alert deduplication** — fires on first day overdue, then weekly (no spam)
- **Pending deletion filter** — skips secrets scheduled for deletion (no false positives)
- **Multi-region replica deduplication** — only alerts from the primary region (no duplicate alerts)
- **New secret protection** — won't flag a new secret as failed until its first rotation is actually overdue

## Architecture

```
EventBridge (daily cron) → Lambda → Secrets Manager (all regions) → SNS → Email
```

## How It Works

1. EventBridge triggers the Lambda daily (default: 9 AM UTC / 4 AM EST)
2. Lambda discovers all AWS regions and scans each for rotation-enabled secrets
3. For each secret:
   - Skips if pending deletion or a multi-region replica
   - Checks `LastRotatedDate` and `CreatedDate` to detect failed rotation
   - Checks `NextRotationDate` to detect upcoming rotation (exact day match)
4. Sends individual SNS notifications per secret with actionable details

### Failed rotation detection logic

| Scenario | Condition | Alert |
|---|---|---|
| Never rotated | No `LastRotatedDate` and past first expected rotation based on `CreatedDate` | FAILED |
| Stopped rotating | `LastRotatedDate` older than rotation interval + 1 day grace | FAILED |
| Healthy | Rotated within expected interval | No alert |

## Prerequisites

- AWS account with Secrets Manager secrets configured for rotation
- Terraform >= 1.0
- AWS CLI configured with appropriate credentials

## Quick Start

```bash
cd secrets-rotation-notifier/terraform
terraform init
terraform apply -var="notification_email=your-email@example.com"
```

Confirm the SNS subscription by clicking the confirmation link in the email from AWS.

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `notification_email` | Yes | — | Email address for notifications |
| `threshold_days` | No | `7` | Days before rotation to send UPCOMING alert |
| `lambda_schedule` | No | `cron(0 9 * * ? *)` | EventBridge schedule expression |

```bash
terraform apply \
  -var="notification_email=team@example.com" \
  -var="threshold_days=10"
```

## Email Examples

### Upcoming rotation

```
Subject: Secret Rotation Alert: my-database-secret (7 days)

Secret Name: my-database-secret
Region: us-east-1
ARN: arn:aws:secretsmanager:us-east-1:123456789012:secret:my-database-secret-AbCdEf
Next Rotation: 2026-04-04 23:59:59 UTC
Days Until Rotation: 7

Action Required:
Prepare to restart/rebuild applications using this secret after rotation completes.
```

### Failed rotation

```
Subject: 🚨 URGENT: Secret Rotation FAILED - my-database-secret

⚠️ ROTATION FAILURE DETECTED ⚠️

Secret Name: my-database-secret
Region: us-east-1
ARN: arn:aws:secretsmanager:us-east-1:123456789012:secret:my-database-secret-AbCdEf
Last Successful Rotation: NEVER
Next Rotation Date: 2026-03-31 23:59:59 UTC
Days Overdue: N/A (never rotated)

ISSUE:
This secret has rotation enabled but has NEVER been successfully rotated.

IMMEDIATE ACTION REQUIRED:
1. Check CloudWatch Logs for the rotation Lambda function
2. Verify the rotation function has proper permissions
3. Ensure network connectivity between Lambda and the database/service
4. Review the troubleshooting guide: https://docs.aws.amazon.com/secretsmanager/latest/userguide/troubleshoot_rotation.html
```

## Customization

**Monitor specific regions only:** Edit `rotation_notifier.py` and modify `get_all_regions()` to return your desired regions.

**Filter specific secrets:** Add tag-based filtering in the `check_secrets_in_region()` function.

**Multiple notification channels:** Extend the SNS topic to include SMS, Slack webhooks, or other targets.

## Cost Estimate

| Resource | Cost |
|---|---|
| Lambda | ~$0.20/month |
| SNS | ~$0.50/month |
| **Total** | **< $1/month** |

## Limitations

- Hourly rotation schedules (`rate(4 hours)`) are not currently supported — the detection logic uses day-level granularity
- UPCOMING alerts use exact day match (`== threshold_days`), so the Lambda must run daily to catch them

## Cleanup

```bash
terraform destroy -var="notification_email=your-email@example.com"
```
