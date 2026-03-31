import boto3
import os
from datetime import datetime, timezone
from typing import List, Dict

THRESHOLD_DAYS = int(os.environ.get('THRESHOLD_DAYS', '7'))
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

def get_all_regions() -> List[str]:
    """Get all AWS regions where Secrets Manager is available."""
    ec2 = boto3.client('ec2', region_name='us-east-1')
    regions = ec2.describe_regions()['Regions']
    return [region['RegionName'] for region in regions]

def check_secrets_in_region(region: str) -> List[Dict]:
    """Check all secrets in a region for upcoming rotations and failed rotations."""
    sm = boto3.client('secretsmanager', region_name=region)
    secrets_to_notify = []
    
    try:
        paginator = sm.get_paginator('list_secrets')
        for page in paginator.paginate():
            for secret in page['SecretList']:
                if 'DeletedDate' in secret:
                    continue
                if 'RotationEnabled' not in secret or not secret['RotationEnabled']:
                    continue
                
                secret_name = secret['Name']
                try:
                    details = sm.describe_secret(SecretId=secret_name)
                    
                    # Skip replica secrets — rotation is managed in the primary region
                    primary_region = details.get('PrimaryRegion')
                    if primary_region and primary_region != region:
                        continue
                    
                    now = datetime.now(timezone.utc)
                    rotation_days = details.get('RotationRules', {}).get('AutomaticallyAfterDays')
                    last_rotated = details.get('LastRotatedDate')
                    next_rotation = details.get('NextRotationDate')
                    
                    # Check for failed rotation
                    if last_rotated is None:
                        # Rotation has never succeeded — but only flag as FAILED
                        # if the first rotation was already due (based on creation date)
                        created_date = details.get('CreatedDate')
                        days_since_created = (now - created_date).days if created_date else 0
                        if rotation_days and days_since_created > rotation_days + 1:
                            days_overdue = days_since_created - rotation_days - 1
                            # Alert on first day overdue, then weekly
                            if days_overdue <= 1 or days_overdue % 7 == 0:
                                secrets_to_notify.append({
                                    'name': secret_name,
                                    'arn': secret['ARN'],
                                    'region': region,
                                    'next_rotation': next_rotation,
                                    'last_rotated': None,
                                    'days_overdue': days_overdue,
                                    'status': 'FAILED'
                                })
                    elif rotation_days and (now - last_rotated).days > rotation_days + 1:
                        # Last successful rotation is older than the rotation interval
                        days_overdue = (now - last_rotated).days - rotation_days - 1
                        # Alert on first day overdue, then weekly
                        if days_overdue <= 1 or days_overdue % 7 == 0:
                            secrets_to_notify.append({
                                'name': secret_name,
                                'arn': secret['ARN'],
                                'region': region,
                                'next_rotation': next_rotation,
                                'last_rotated': last_rotated,
                                'days_overdue': days_overdue,
                                'status': 'FAILED'
                        })
                    # Check for upcoming rotation
                    elif next_rotation:
                        days_until = (next_rotation - now).days
                        if days_until == THRESHOLD_DAYS:
                            secrets_to_notify.append({
                                'name': secret_name,
                                'arn': secret['ARN'],
                                'region': region,
                                'next_rotation': next_rotation,
                                'days_until': days_until,
                                'status': 'UPCOMING'
                            })
                
                except Exception as e:
                    print(f"Error checking secret {secret_name} in {region}: {str(e)}")
                    continue
    
    except Exception as e:
        print(f"Error listing secrets in {region}: {str(e)}")
    
    return secrets_to_notify

def send_notification(secrets: List[Dict]):
    """Send SNS notification for secrets approaching rotation or with failed rotation."""
    if not secrets:
        return
    
    sns = boto3.client('sns')
    
    for secret in secrets:
        status = secret.get('status', 'UPCOMING')
        
        if status == 'FAILED':
            subject = f"🚨 URGENT: Secret Rotation FAILED - {secret['name']}"
            
            last_rotated_str = secret['last_rotated'].strftime('%Y-%m-%d %H:%M:%S UTC') if secret['last_rotated'] else 'NEVER'
            
            if secret['last_rotated'] is None:
                issue_detail = "This secret has rotation enabled but has NEVER been successfully rotated."
                overdue_line = "Days Overdue: N/A (never rotated)"
            else:
                issue_detail = (
                    "This secret's last successful rotation is older than its configured rotation interval, "
                    "indicating that recent rotation attempts have failed."
                )
                overdue_line = f"Days Overdue: {secret['days_overdue']}"
            
            message = f"""⚠️ ROTATION FAILURE DETECTED ⚠️

Secret Name: {secret['name']}
Region: {secret['region']}
ARN: {secret['arn']}
Last Successful Rotation: {last_rotated_str}
Next Rotation Date: {secret['next_rotation'].strftime('%Y-%m-%d %H:%M:%S UTC') if secret['next_rotation'] else 'N/A'}
{overdue_line}

ISSUE:
{issue_detail}

IMMEDIATE ACTION REQUIRED:
1. Check CloudWatch Logs for the rotation Lambda function
2. Verify the rotation function has proper permissions
3. Ensure network connectivity between Lambda and the database/service
4. Review the troubleshooting guide: https://docs.aws.amazon.com/secretsmanager/latest/userguide/troubleshoot_rotation.html

IMPACT:
Applications using this secret may be using outdated credentials, which could lead to:
- Authentication failures
- Service disruptions
- Security compliance violations

This is an automated alert from AWS Secrets Manager Rotation Notifier.
"""
        else:
            subject = f"Secret Rotation Alert: {secret['name']} ({secret['days_until']} days)"
            
            message = f"""Secret Name: {secret['name']}
Region: {secret['region']}
ARN: {secret['arn']}
Next Rotation: {secret['next_rotation'].strftime('%Y-%m-%d %H:%M:%S UTC')}
Days Until Rotation: {secret['days_until']}

Action Required:
Prepare to restart/rebuild applications using this secret after rotation completes.

This is an automated notification from AWS Secrets Manager Rotation Notifier.
"""
        
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject,
                Message=message
            )
            print(f"Notification sent for {secret['name']} in {secret['region']} (Status: {status})")
        except Exception as e:
            print(f"Error sending notification for {secret['name']}: {str(e)}")

def lambda_handler(event, context):
    """Main Lambda handler."""
    print(f"Starting rotation check with {THRESHOLD_DAYS} day threshold")
    
    regions = get_all_regions()
    print(f"Checking {len(regions)} regions")
    
    all_secrets = []
    for region in regions:
        secrets = check_secrets_in_region(region)
        all_secrets.extend(secrets)
    
    failed_count = sum(1 for s in all_secrets if s.get('status') == 'FAILED')
    upcoming_count = sum(1 for s in all_secrets if s.get('status') == 'UPCOMING')
    
    print(f"Found {failed_count} secrets with failed rotation")
    print(f"Found {upcoming_count} secrets with upcoming rotation")
    
    send_notification(all_secrets)
    
    return {
        'statusCode': 200,
        'body': f'Checked {len(regions)} regions, sent {len(all_secrets)} notifications ({failed_count} failed, {upcoming_count} upcoming)'
    }
