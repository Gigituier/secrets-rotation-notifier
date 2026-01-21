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
    """Check all secrets in a region for upcoming rotations."""
    sm = boto3.client('secretsmanager', region_name=region)
    secrets_to_notify = []
    
    try:
        paginator = sm.get_paginator('list_secrets')
        for page in paginator.paginate():
            for secret in page['SecretList']:
                if 'RotationEnabled' not in secret or not secret['RotationEnabled']:
                    continue
                
                secret_name = secret['Name']
                try:
                    details = sm.describe_secret(SecretId=secret_name)
                    
                    if 'NextRotationDate' not in details:
                        continue
                    
                    next_rotation = details['NextRotationDate']
                    now = datetime.now(timezone.utc)
                    days_until = (next_rotation - now).days
                    
                    if days_until == THRESHOLD_DAYS:
                        secrets_to_notify.append({
                            'name': secret_name,
                            'arn': secret['ARN'],
                            'region': region,
                            'next_rotation': next_rotation,
                            'days_until': days_until
                        })
                
                except Exception as e:
                    print(f"Error checking secret {secret_name} in {region}: {str(e)}")
                    continue
    
    except Exception as e:
        print(f"Error listing secrets in {region}: {str(e)}")
    
    return secrets_to_notify

def send_notification(secrets: List[Dict]):
    """Send SNS notification for secrets approaching rotation."""
    if not secrets:
        return
    
    sns = boto3.client('sns')
    
    for secret in secrets:
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
            print(f"Notification sent for {secret['name']} in {secret['region']}")
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
    
    print(f"Found {len(all_secrets)} secrets requiring notification")
    
    send_notification(all_secrets)
    
    return {
        'statusCode': 200,
        'body': f'Checked {len(regions)} regions, sent {len(all_secrets)} notifications'
    }
