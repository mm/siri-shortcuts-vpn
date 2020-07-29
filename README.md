# VPN on Demand with Siri, Shortcuts, Python, AWS EC2 & Lambda

This is the Python code referenced in my [dev.to](https://dev.to/mmascioni/tutorial-vpn-on-demand-with-siri-shortcuts-python-aws-ec2-lambda-i83) post on how to launch a VPN on the fly (using AWS EC2 servers) by combining some AWS Lambda, API Gateway and Shortcuts magic (also available in [this repository](post.md)). This is more of a proof-of-concept than anything else, although it's a tool I've used myself so I wanted to make it available for everyone. Please open issues or shoot me an email with any suggestions on how to improve this further! ❤️

## Using this code locally:

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

6. If everything is in order, you should be able to run `python3 app.py` in the root directory to start up the Flask development server. Look out for the command's output. By default, the server will be listening for connections on port 5000.

7. Try making HTTP requests to your server! You can use cURL, [httpie](https://httpie.org), [Paw](https://paw.cloud), [Postman](https://www.postman.com) or any API testing tool you'd like. For example, if I was trying to deploy instances in the US-East-1 region (and that's where my launch template was stored), with cURL I'd make this request to try starting up:

```console
$ curl -X POST http://localhost:5000/instances/us-east-1
```

If successful I should get a response like this:

```
{"instance_id":"i-some-instance-id","ip":"<some ip address>","region":"us-east-1"}
```

Getting running instances can be done via a GET request (i.e. ```curl -X GET http://localhost:5000/instances/us-east-1```) and terminating instances in a region can be done via a DELETE request (```curl -X DELETE http://localhost:5000/instances/us-east-1```). The code attempts to make sure only 1 instance is running at a time (to protect against accidentally starting many instances at once) -- so DELETE works as intended (deletes the whole collection of instances, but that collection is only supposed to contain 1 instance at a time).