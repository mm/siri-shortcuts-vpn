import boto3
import time

def launch_instance(launch_template_name, region='us-east-1'):
    """Launches an EC2 instance purposed for an on-the-fly VPN,
    based on a launch template defined earlier. Note that the template
    corresponding to ```launch_template_name``` must already exist.

    Returns a two-member tuple of (Instance ID, Instance IP Address),
    or None if unsuccessful.

    Arguments:
    launch_template_name -- The name of the EC2 launch template
    region -- The AWS region to deploy the VPN in (default: us-east-1)
    """
    
    s = boto3.client('ec2', region_name=region)
    try:
        response = s.run_instances(
            MinCount=1,
            MaxCount=1,
            LaunchTemplate={
                'LaunchTemplateName': launch_template_name
            }
        )
        instance_id = response['Instances'][0]['InstanceId']
        time.sleep(2)  # As it turns out, sometimes it takes time for an IP to be assigned
        instance = boto3.resource('ec2', region_name=region).Instance(instance_id)
        return (instance_id, instance.public_ip_address)
    except Exception as e:
        print(f'Error creating instance: {e}')
        return None

def list_instances(region='us-east-1'):
    """Returns a list of dicts describing running EC2 instances
    (tagged as VPNs). The `id` key represents the instance ID (InstanceId)
    and the `ip` key represents the instance's public IPv4 address (PublicIpAddress)

    Arguments:
    region -- The AWS region to check for instances in (default: us-east-1)
    """

    s = boto3.client('ec2', region_name=region)
    response = s.describe_instances(
        Filters=[
            {
                'Name': 'instance-state-name',
                'Values': ['running', 'pending']
            },
            {
                'Name': 'tag:instance_type',
                'Values': ['vpn']
            }
        ]
    )
    reservations = response.get('Reservations')
    instances = []
    if reservations:
        try:
            instances = [{'id': x['Instances'][0]['InstanceId'], 'ip': x['Instances'][0]['PublicIpAddress']} for x in reservations]
        except Exception as e:
            print(f'Error fetching instance list: {e}')
            raise
    return instances

def terminate_instances(region='us-east-1'):
    """Terminates all active VPN instances (only one should be running at
    a time in a given region by default).

    Returns the number of instances terminated.

    Arguments:
    region -- The AWS region to check for instances in (default: us-east-1)
    """

    s = boto3.client('ec2', region_name=region)
    # Get currently running VPNs:
    instances = list_instances(region=region)
    instance_ids = [x['id'] for x in instances]

    # Terminate any all at once:
    if len(instance_ids) > 0:
        try:
            response = s.terminate_instances(
                InstanceIds=instance_ids
            )
            return len(response['TerminatingInstances'])
        except Exception as e:
            print(e)
            return 0
    return 0