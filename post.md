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

