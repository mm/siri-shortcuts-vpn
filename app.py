from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import ec2_vpn

if not os.getenv('AWS_EXECUTION_ENV'):
    # Not running in the Lambda execution environment, we're
    # testing locally so load environment variables for our
    # AWS credentials and such:
    load_dotenv()

app = Flask(__name__)

@app.route('/instances', methods=['GET', 'POST', 'DELETE'])
def manage_instances():
    # Get the AWS region from the aws-region header.
    # If one wasn't specified, we default to us-east-1:
    region = request.headers.get('aws-region', 'us-east-1')
    instances = ec2_vpn.list_instances(region=region)
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
            )
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