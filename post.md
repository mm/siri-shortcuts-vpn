# VPN on demand with Siri, Shortcuts, Python, AWS EC2 & Lambda

Sometimes you need a VPN for a short period of time (like when you'll be on public Wi-Fi for a little while). [Amazon EC2](https://aws.amazon.com/ec2/) makes deploying servers to be used as VPNs for this purpose pretty simple and cost-effective since you're only charged from the time you start until the instance's termination. Open-source projects like [setup-ipsec-vpn](https://github.com/hwdsl2/setup-ipsec-vpn) make this even easier. However, this requires you to get onto the AWS Console to get everything set up, which can be a bit of a pain. The motivation for this project was to be able to do this:

![Asking Siri to create a VPN for me, then returning the VPN's IP address to connect to]()

To do this, we're going to be deploying some Python code as a Lambda function with AWS. This code will start/stop EC2 instances for us and run the [setup-ipsec-vpn](https://github.com/hwdsl2/setup-ipsec-vpn) script on them automatically. We'll use AWS [API Gateway](https://aws.amazon.com/api-gateway/) to create a RESTful API that will trigger this function. Then, we'll use Apple's [Shortcuts](https://apps.apple.com/us/app/shortcuts/id915249334) app to make a request to the API endpoint we create. 

## What you need:

* An [Amazon AWS account](https://aws.amazon.com). If this is your first time signing up, you'll be eligible for the [free tier](https://aws.amazon.com/free/?all-free-tier.sort-by=item.additionalFields.SortRank&all-free-tier.sort-order=asc). 
* A computer with [Python 3](https://python.org) and the [AWS CLI](https://aws.amazon.com/cli/) installed and [configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
* An iOS device with the [Shortcuts](https://apps.apple.com/us/app/shortcuts/id915249334) app installed

## Limitations/Disclaimer

* The Python function will limit you to deploying only in one AWS region at a time, since EC2 Launch Templates (which we'll use) are tied to a region. Here we use `us-east-1` as our region.

* About AWS charges: Some of the services used in this post are intended to fall within the free tier usage, however some do not. Lambda offers 1 million Lambda requests every month even once your free-tier access expires, while API Gateway only offers 1 million requests per month for the first year, and EC2 offers 750 hours per month on t2.micro instances (what we're using) for the first year. Make sure to review pricing for [Lambda](https://aws.amazon.com/lambda/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/) and [EC2](https://aws.amazon.com/ec2/pricing/on-demand/) before continuing.

Let's get started!

## Creating the EC2 Launch Template

EC2 Launch Templates are a great way to save a frequently used EC2 launch configuration (i.e. instance type, security groups, firewall rules, storage, etc.). In our case our launch template will have all the necessary configuration necessary to deploy an EC2 instance as a VPN for us.

1. Sign into your [AWS Console](https://console.aws.amazon.com) and ensure you're in the region you want to deploy your VPNs to (you can see this at the top right of the screen). In this guide we use ```us-east-1```.

2. First, we'll set up a **Security Group**, which contains the firewall rules for our EC2 instance. On the left side of the page, click on "Security Groups" under "Network and Security. Click "Create Security Group".

3. Give your group a name, leave the VPC dropdown at its default, and set the following *inbound* UDP rules (leave Outbound at its default): this will allow you to connect to your server.

![Opening up UDP ports 500 and 4500](img/inbound_rules.png)

(Note: For greater security, you can restrict `Source` further here: perhaps to a range of IP addresses)

4. Save the security group. Next we'll create a key pair, useful if you want to SSH into your instance in the future. Under "Network & Security", click on "Key Pairs".

5. Click "Create Key Pair" and follow the instructions (if you already have set up one, you can use that key pair instead for the remainder of this guide)

6. Now we'll create our launch template. Under "Instances", click on "Launch Templates", and then "Create launch template". Give the template a name, and begin filling out the form. For the AMI, I chose one that corresponded to Ubuntu 20.04. I filled out the following details:

```
Instance Type: t2.micro (Free Tier eligible)
Key pair: The key pair you created in step (5)
Security groups: The security group you created in step (3)
Storage (volumes): Click "Add new volume". Make sure "Delete on termination" is set to Yes, and leave everything else at default.
```

7. Under "Resource tags", click "Add tag" and set a key of `instance_type` to `vpn`. Leave "Resource types" at its default (should have "Instances" selected). This will cause EC2 instances deployed with this template to be tagged, which lets us keep them separate from other instances and let our Lambda function terminate the right instance.

8. Under "Advanced details", scroll to "User data". This is where we'll put the script from [hwdsl2/setup-ipsec-vpn](https://github.com/hwdsl2/setup-ipsec-vpn#installation) in. Make sure to put `#!/bin/bash` at the top of the script since this is being executed in a Bash shell. It's executed when your instance is booted for the first time. To find out more about User Data, check the [Amazon docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html#user-data-shell-scripts) on it.

![User data to input to your template](img/user_data.png)

Fill out `VPN_IPSEC_PSK`, `VPN_USER` and `VPN_PASSWORD` with an IPSec PSK, a VPN username and password. Generate these and store them in a password manager. 

9. Save the launch template and note the name you gave to it. Also note the launch template ID. If you'd like to test and see if it works, you can [launch an EC2 instance based on it](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html)! Follow the connection instructions [here](https://github.com/hwdsl2/setup-ipsec-vpn/blob/master/docs/clients.md) after it's been up and running for a few minutes. 

Otherwise, let's move on to the Lambda part of the project!

## Setting up our Lambda function

[Amazon Lambda](https://aws.amazon.com/lambda/) is a service that allows you to write code and execute it using various triggers (here we use an HTTP request). What's so neat about it is you're only charged for the time and resources your code uses while it runs, saving quite a bit. Here, we're using some Python code to automatically launch an EC2 instance based on the template we defined above (or terminate/list instances).

I've already written the code and you can check it out on [GitHub here](https://github.com/mm/siri-shortcuts-vpn). It uses the [Flask](https://flask.palletsprojects.com/en/1.1.x/) framework to define a tiny API that can receive HTTP requests and act on them accordingly. We'll package this up and deploy it as a Lambda function with the popular [Zappa](https://github.com/Miserlou/Zappa) package a little later.

### Creating the necessary IAM policy

For Lambda to be able to perform EC2 actions on your behalf (starting servers up, shutting them down...) it needs permissions to do so. When using AWS, we define these permissions by an [IAM policy](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html). We'll set one up here:

1. Log in to your AWS Console > Services > IAM. Select "Policies" from the sidebar, and then "Create policy". Switch from the visual editor to JSON mode and paste this policy in:

```json
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Sid": "VisualEditor0",
			"Effect": "Allow",
			"Action": "ec2:Describe*",
			"Resource": "*"
		},
		{
			"Effect": "Allow",
			"Action": [
				"ec2:RunInstances",
				"ec2:CreateTags"
			],
			"Resource": "*",
			"Condition": {
				"ArnLike": {
					"ec2:LaunchTemplate": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:launch-template/LAUNCH_TEMPLATE_ID"
				},
				"Bool": {
          "ec2:IsLaunchTemplateResource": "true"
        }
			}
		},
		{
			"Sid": "VisualEditor2",
			"Effect": "Allow",
			"Action": "ec2:CreateTags",
			"Resource": "arn:aws:ec2:*:ACCOUNT_ID:instance/*",
			"Condition": {
				"StringEquals": {
					"ec2:CreateAction": "RunInstances"
				}
			}
		},
		{
			"Sid": "VisualEditor3",
			"Effect": "Allow",
			"Action": [
				"ec2:TerminateInstances",
				"ec2:StartInstances",
				"ec2:StopInstances"
			],
			"Resource": "*",
			"Condition": {
				"StringEquals": {
					"ec2:ResourceTag/instance_type": "vpn"
				}
			}
		}
	]
}
```

Fill in the `AWS_REGION`, `ACCOUNT_ID` and `LAUNCH_TEMPLATE_ID` with the AWS region you made your EC2 launch template in (for example, I used `us-east-1`), your AWS account ID (numeric) and your launch template ID from the last section.

This policy allows your function to describe details about any EC2 instance, create new instances *only* from your launch template, create tags on any instance, and only start/stop/terminate instances tagged as VPNs. For more examples of policies if you're interested (as they relate to EC2 instances), [Amazon's docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ExamplePolicies_EC2.html#iam-example-runinstances) have a wealth of info.

### Creating a test IAM user with the IAM policy

This step is technically optional, but it allows you to test out the code locally before deploying. Here we'll create an IAM *user* and attach our *policy* to it. 

1. Log in to your AWS Console > Services > IAM. Select "Users" from the sidebar, and click "Add user".

2. Give the user a username (doesn't matter) and make sure **Programmatic access** is checked.

3. Click Next, and click "Attach existing policies directly". Search for your policy, ensure it's checked and click Next again. You can leave tags blank. Finally, click Create user. Make note of the *Access key ID* and *Secret access key* -- we will be using these shortly.

### Working with the code locally

With all of the policy setup out of the way, we're ready to go! Now, we'll deploy a web service I wrote using Flask to Lambda. First, we'll test the code locally, and once it's working, we'll use [Zappa](https://github.com/Miserlou/Zappa) to automate deployment. These instructions are also on my [GitHub repo](https://github.com/mm/siri-shortcuts-vpn) for this project.

1. Ensure you've installed the [AWS CLI](https://aws.amazon.com/cli/), [configured your environment](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html) and have Python 3 and pip ready to go for local development. 

2. Clone this repository in a directory of your choosing: `git clone git@github.com:mm/siri-shortcuts-vpn.git`

3. I recommend setting up a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/) for this project to keep its dependencies/versions of those dependencies separate from other projects. 

4. Install the packages this code relies on: `pip install -r requirements.txt`

5. Create an `.env` file at the root level of the project and fill in the following environment variables. This will allow you to simulate using the IAM policy you created in tutorial to ensure it works before deploying.

```
AWS_ACCESS_KEY_ID=ACCESS_KEY_ID_YOU_JUST_CREATED
AWS_SECRET_ACCESS_KEY=SECRET_ACCESS_KEY_YOU_JUST_CREATED
AWS_DEFAULT_REGION=fill_in_your_aws_region_here
LAUNCH_TEMPLATE_NAME=fill_in_your_launch_template_name_here
```

6. If everything is in order, you should be able to run ```python3 app.py``` in the root directory to start up the Flask development server. Look out for the command's output. By default, the server will be listening for connections on port 5000.

7. Try making HTTP requests to your server! You can use cURL, [httpie](https://httpie.org), [Paw](https://paw.cloud), [Postman](https://www.postman.com) or any API testing tool you'd like. For example, if I was trying to deploy instances in the US-East-1 region (and that's where my launch template was stored), with cURL I'd make this request to try starting up:

```bash
curl -X POST http://localhost:5000/instances/us-east-1
```

If successful I should get a response like this:

```
{"instance_id":"i-some-instance-id","ip":"<some ip address>","region":"us-east-1"}
```

Getting running instances can be done via a GET request (i.e. ```curl -X GET http://localhost:5000/instances/us-east-1```) and terminating instances in a region can be done via a DELETE request (```curl -X DELETE http://localhost:5000/instances/us-east-1```). The code attempts to make sure only 1 instance is running at a time (to protect against accidentally starting many instances at once) -- so DELETE works as intended (deletes the whole collection of instances, but that collection is only supposed to contain 1 instance at a time).

Once you're sure everything is working okay, let's deploy to Lambda!

## Deploying to Lambda and API Gateway