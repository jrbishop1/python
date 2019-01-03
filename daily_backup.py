import json
import boto3
import datetime
from botocore.exceptions import ClientError
import os

#my_region = os.environ['REGION']

sns_client = boto3.client('sns')

def aws_session(role_arn=None, session_name='my_session'):
    if role_arn:
        sts_client = boto3.client('sts')
        response = sts_client.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
        session = boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken'])
        return session
    else:
        return boto3.Session()

def lambda_handler(event, context):
    event_role_arn = event['rolearn']
    session_assumed = aws_session(role_arn=event_role_arn, session_name='my_lambda')
    session_regular = aws_session()
    #print(session_assumed.client('ec2').get_caller_identity()['Account'])
    #print(session_regular.client('ec2').get_caller_identity()['Account'])
    
    regions = ['us-east-1', 'us-west-2', 'ap-northeast-1', 'us-east-2']
    
    for region in regions:
        print('\nThe following backups are being taken in the {0} region:\n'.format(region))
    
        instances = session_assumed.client('ec2', region_name=region).describe_instances(Filters=[{'Name': 'tag:Backup', 'Values': ['daily']}])
        
        for instance in instances['Reservations']:
            for i in instance['Instances']:
                for tag in i['Tags']:
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                block_devices = i['BlockDeviceMappings']
                for vol in block_devices:
                    volume_id = vol['Ebs']['VolumeId']
                    description = 'daily-backup-%s.%s' % (instance_name, volume_id)
                    print(description)
                    session_assumed.client('ec2', region_name=region).create_snapshot(VolumeId=volume_id, Description=description, DryRun=False)

        snapshots = session_assumed.client('ec2', region_name=region).describe_snapshots()
        for snapshot in snapshots['Snapshots']:
            retention_days = 5
            if snapshot['Description'].startswith('daily-backup') and ( datetime.datetime.now().replace(tzinfo=None) - snapshot['StartTime'].replace(tzinfo=None) ) > datetime.timedelta(days=retention_days):
                try:
                    snap_description = snapshot['Description']
                    snap_id = snapshot['SnapshotId']
                    print('Deleting {0}-{1}'.format(snap_description, snap_id))
                    #session_assumed.client('ec2', region_name=region).delete_snapshot(SnapshotId=snap_id)
                    #print("Deleted snapshot [%s - %s]" % ( snapshot.snapshot_id, snapshot.description ))
                except ClientError as e:
                    if e.response['Error']['Code'] == 'InvalidSnapshot.InUse':
                        print("Snapshot in use")
                    else:
                        print("Unexpected error occurred")


                        
