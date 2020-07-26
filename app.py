import os

import boto3
from botocore.exceptions import ClientError
from flask import Flask, jsonify, request
from dotenv import load_dotenv

import ec2_vpn

if not os.getenv('AWS_EXECUTION_ENV'):
    # Not running in the Lambda execution environment, we're
    # testing locally so load environment variables for our
    # AWS credentials and such:
    load_dotenv()

app = Flask(__name__)

@app.errorhandler(ClientError)
def handle_boto_client_error(e):
    """Error handling to alert user if IAM policy hasn't
    been set up properly
    """
    # Get response code:
    code = e.response['Error']['Code']
    if code == "UnauthorizedOperation":
        return jsonify(error="Your user or role didn't have the right permissions to perform that action: check your IAM policy!")
    else:
        return jsonify(error=f"AWS Client Error: {code}")


@app.route('/instances/<string:region>', methods=['GET', 'POST', 'DELETE'])
def manage_instances(region):
    # Build a list of valid AWS regions (e.g us-east-1) for EC2.
    # These will be validated for every request:
    region_response = boto3.client('ec2').describe_regions()
    aws_regions = [endpoint['RegionName'] for endpoint in region_response['Regions']]

    # Get the AWS region from the URL, and validate it:
    if region not in aws_regions:
        return jsonify(error=f"Region {region} is not a valid AWS region name for EC2."), 400
    # If it's valid, fetch a list of instances outright (more than one method
    # uses this list so we'll factor it out):
    try:
        instances = ec2_vpn.list_instances(region=region)
    except ClientError:
        raise
    except Exception as e:
        print(f"Error fetching instances: {e}")
        return jsonify(error="An error occured while fetching the list of running instances"), 500
    
    # This should correspond to a valid EC2 launch template in the region of interest:
    template = os.getenv('LAUNCH_TEMPLATE_NAME')

    if request.method == 'GET':
        # If we receive a GET request, then list
        # all the currently running instances (shouldn't
        # be > 1 in a region
        return jsonify(region=region, running_instances=instances)
    elif request.method == 'POST':
        # Start up a new instance:
        if not template:
            return jsonify(
                error="Please set the LAUNCH_TEMPLATE_NAME Lambda environment variable first."
            ), 500
        
        if len(instances) == 0:
            new_instance = ec2_vpn.launch_instance(template, region=region)
            return jsonify(
                region=region,
                instance_id=new_instance[0],
                ip=new_instance[1]
            ), 200
        else:
            return jsonify(error=f"An instance is already running in the {region} region. Please terminate it first"), 429
    elif request.method == 'DELETE':
        # We've received a DELETE request, so terminate any VPN EC2 instances:
        instances_removed = ec2_vpn.terminate_instances(region=region)
        return jsonify(
            region=region,
            instances_terminated=instances_removed
        )
    else:
        return jsonify(error="Method not implemented"), 501

if __name__ == '__main__':
    app.run()