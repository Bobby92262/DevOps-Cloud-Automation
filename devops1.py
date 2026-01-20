#!/usr/bin/env python3
import boto3
import uuid
import json
import subprocess
import time
from datetime import datetime

ec2 = boto3.resource('ec2')

# Create unique bucket name
short_id= str(uuid.uuid4())[:6]
bucket_name = f"{short_id}-xxxx" # bucket name
#Specify region
region = "us-east-1"
#S3 URL
s3_url = f"http://{bucket_name}.s3-website-{region}.amazonaws.com"

# Bucket creation
s3 = boto3.resource("s3")
s3client = boto3.client("s3")
# response 1 is bucket creation
# response2 is removal of public access block
try:
	response = s3.create_bucket(Bucket=bucket_name)
	response2 = s3client.delete_public_access_block(Bucket=bucket_name)
	print (f"Bucket created: {response}\n Public access enabled: {response2}")
except Exception as error:
	print (f"Error in creating bucket: {error}")

# Static website hosting
website_configuration = {
	'ErrorDocument': {'Key': 'error.html'}, #Fallback page
	'IndexDocument': {'Suffix': 'index.html'}, #Set index as homepage
}

try:
	bucket_website = s3.BucketWebsite(bucket_name)
	response = bucket_website.put(WebsiteConfiguration=website_configuration)
	print("Static website hosting enabled")
except Exception as error:
	print(f"Error with website config: {error}")

# Apply public access to bucket
bucket_policy = {
    "Version": "2012-10-17",
    "Statement": [
		{
		"Sid": "PublicReadGetObject",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource":[f"arn:aws:s3:::{bucket_name}/*"]
		}
	]
}

try:
	s3.Bucket(bucket_name).Policy().put(Policy=json.dumps(bucket_policy))
	print("Bucket policy applied")
except Exception as error:
	print(f"Error applying bucket policy: {error}")


# User data script
user_data= f"""#!/bin/bash
yum update -y
echo "Installing Apache..."
yum install httpd -y
echo "Apache installed"
echo "Installing aws-cli"
yum install -y aws-cli
echo "aws-cli installed"
systemctl enable httpd
systemctl start httpd
echo "Apache server started"

echo '<html>' > index.html
echo '<body>' >> index.html

TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s)

echo -e "<p><strong>Instance ID:</strong> $(curl -s -H \"X-aws-ec2-metadata-token: $TOKEN\" http://169.254.169.254/latest/meta-data/instance-id)</p>" >> index.html

echo -e "<p><strong>Private IP:</strong> $(curl -s -H \"X-aws-ec2-metadata-token: $TOKEN\" http://169.254.169.254/latest/meta-data/local-ipv4)</p>" >> index.html

echo -e "<p><strong>Instance Type:</strong> $(curl -s -H \"X-aws-ec2-metadata-token: $TOKEN\" http://169.254.169.254/latest/meta-data/instance-type)</p>" >> index.html

echo -e "<p><strong>Availability Zone:</strong> $(curl -s -H \"X-aws-ec2-metadata-token: $TOKEN\" http://169.254.169.254/latest/meta-data/placement/availability-zone)</p>" >> index.html

echo -e '<!-- IMAGE_PLACEHOLDER -->' >> index.html

echo -e '</body>\n</html>' >> index.html

mkdir -p /var/www/html

cp index.html /var/www/html/index.html

chmod 644 /var/www/html/index.html

"""

# Create list of instances
try:
	instances = ec2.create_instances (
		ImageId='YOUR_AMI_ID_HERE', #Enter an AMI here
		KeyName='YOUR_KEYPAIR_NAME', # Name of ssh key
		SecurityGroupIds=['sg-REPLACE_ME'], # SG id
		MinCount=1,
		MaxCount=1,
		InstanceType='t2.nano',
		Placement={'AvailabilityZone': 'YOUR_AZ'}, # Specify region
		UserData=user_data,
		TagSpecifications=[
			{
				'ResourceType':'instance',
				'Tags': [
					{'Key':'Name', 'Value': 'Web Server'}
				]
			}
   		]
	)
	print ("EC2 instance launched")
except Exception as error:
	print (f"Error launching EC2 instance: {error}")

# Instance waiters
try:
	instance = instances[0]
	instance.wait_until_exists()
	print ("Instance is pending")
	instance.wait_until_running()
	print ("Instance Running")
	instance.reload()
	public_dns = instance.public_dns_name
	ec2_url = f"http://{public_dns}/"
except Exception as error:
	print (f"Error waiting for instance: {error}")

#Write URLs to local file
with open("FILE_NAME.txt", "w") as f: # Specify file name
	f.write(f"EC2 Website: {ec2_url}\n")
	f.write(f"S3 Website: {s3_url}\n")

#AMI Creation
initials = "XX" # Initials
timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S%f")
ami_name = f"{initials}-{timestamp}"
try:
	image = instance.create_image(
		Name=ami_name,
		Description='AMI image',
		NoReboot=True
)
	image.wait_until_exists()
	print (f"Created AMI ID: {image.id}")
except Exception as error:
	print (f"Error creating AMI: {error}")

#Enable EventBridge Notifications on S3
notification_config = json.dumps({ "EventBridgeConfiguration": {} })
try:
	subprocess.run(["aws","s3api","put-bucket-notification-configuration","--bucket",f"{bucket_name}","--notification-configuration",notification_config],check=True)
	print ("EventBridge enabled")
except subprocess.CalledProcessError as error:
    print (f"EventBridge enabling failed ! ")

#Create an SNS topic
try:
	result = subprocess.run(["aws","sns","create-topic","--name","YOUR_TOPIC_NAME"],capture_output=True, text=True, check=True) # Hide naming conventions
	print ("SNS topic created")
    #Parse the ARN from the JSON response
	topic_arn = json.loads(result.stdout)["TopicArn"]
	print (f"Created topic ARN: {topic_arn}")
except subprocess.CalledProcessError as error:
	print (f"SNS topic creation failed: {error}")

# Subscribe an Email Address
sub_email = "SUBSCRIPTION_EMAIL" # Email to subscribe
try:
	subprocess.run(["aws","sns","subscribe","--topic-arn",topic_arn,"--protocol","email","--notification-endpoint",sub_email],check=True)
	print (f"Check your email for subscription link: {sub_email}, you have 90 seconds")
	time.sleep(90)
except subprocess.CalledProcessError as error:
	print (f"There was an issue with SNS subscription: {error}")

#Create EventBridge rule
rule = json.dumps({
	"source": ["aws.s3"],
	"detail-type": ["Object Created", "Object Removed"],
	"detail": {
		"bucket": {
			"name": [f"{bucket_name}"]
        }
    }
})
try:
	subprocess.run(["aws","events","put-rule","--name","S3ImageEventRule","--event-pattern",rule],check=True)
	print ("Event rule has been created")
except subprocess.CalledProcessError as error:
	print (f"Event rule failed to be created: {error}")

# Retrieve Account ID
try:
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    print(f"AWS Account ID: {account_id}")
except Exception as error:
    print (f"Failed to get account ID: {error}")


# Attach the SNS Topic as a Target
role_arn = f"arn:aws:iam::{account_id}:role/xxxx" # Lab role 
trgt_cmd = json.dumps([
    {
        "Id": "SendImageAlert",
        "Arn": topic_arn,
		"RoleArn": role_arn
    }
])
try:
	subprocess.run(["aws","events","put-targets","--rule","S3ImageEventRule","--targets",trgt_cmd],check=True)
	print ("Target attached to rule successfully")
except subprocess.CalledProcessError as error:
	print (f"Target did not attach to rule. Failure: {error}")

# Uploading of image pulled from web
image_url = "IMAGE_URL" #Image URL to be loaded in

local_path = "FILE_PATH" # Path for image

public_dns = instance.public_dns_name

img_tag = f'<img src=\\"https://{bucket_name}.s3.amazonaws.com/saved_image.jpg\\" alt=\\"Logo\\">'

key_path = "KEY_PATH" # Location of key storage

#Command to replace the image placeholder tag with the actual img src
ssh_cmd = [
	"ssh","-o","StrictHostKeyChecking=no","-i",key_path,
	f"ec2-user@{public_dns}",f"sudo sed -i 's|<!-- IMAGE_PLACEHOLDER -->|{img_tag}|' /var/www/html/index.html"
]
#Command to check theat appache server is running and reeady for image inection
ssh_check_cmd = [
	"ssh","-o","StrictHostKeyChecking=no","-i",key_path,
    f"ec2-user@{public_dns}","systemctl is-active httpd"
]

#Dynamic download of image from URL
try:
	subprocess.run(["curl","-s",image_url,"-o",local_path],check=True)
	print ("Image downloaded successfully")
except subprocess.CalledProcessError as error:
	print (f"Error downloading image: {error}")

#Upload the image to the s3 bucket // API call and boto calls not CLI 
try:
	subprocess.run([
		"aws","s3","cp",local_path,f"s3://{bucket_name}/saved_image.jpg","--content-type","image/jpeg"], check=True)
	print ("Image uploaded to s3")
except subprocess.CalledProcessError as error:
	print (f"Error uploading image to s3: {error}")


#Check apache server is running before injection of <img> tag
apache_ready=False
print("Checking if Apache is active...")

for attempt in range(10):
    try:
        result = subprocess.run(ssh_check_cmd, capture_output=True,text=True)
        if result.stdout.strip() == "active":
            print ("Apache is running.")
            apache_ready=True
            break
    except subprocess.CalledProcessError:
        print (f"Attempt {attempt+1}: Apache not ready yet.")
    time.sleep(5)
if not apache_ready:
    print ("Apache is not active within the timeout. Skipping image injection")
else:
#Inject image to placeholder tag
	try:
		print ("Waiting 90 seconds for EC2 to finish booting...")
		#time.sleep(90)
		subprocess.run(ssh_cmd, check=True)
		print ("Image tag injected into index.html")
	except subprocess.CalledProcessError as error:
		print (f"Error injecting image tag: {error}")

#Copy EC2 index.html
try:
	subprocess.run([
    "scp","-i",key_path,f"ec2-user@{public_dns}:/var/www/html/index.html","index.html"], check=True)
	print ("Image successfully downloaded")
except subprocess.CalledProcessError as error:
	print (f"Error copying from ec2 instance: {error}")

#Upload to S3 bucket
try:
	subprocess.run([
    "aws", "s3", "cp", "index.html", f"s3://{bucket_name}/index.html","--content-type"," text/html"], check=True)
	print ("Copied index.html to  s3 bucket")
except subprocess.CalledProcessError as error:
	print (f"Error injecting index.html: {error}")

#write error.html
try:
	with open("error.html","w") as f:
		f.write("<h1>Error!, Something went wrong.</h1>")
	print ("error.html created successfully")
except Exception as error:
	print (f"Error creating error.html: {error}")

#Upload error.html to bucket
try:
	subprocess.run([
	"aws","s3","cp","error.html",f"s3://{bucket_name}/error.html","--content-type","text/html"])
	print ("Uploaded error.html successfully")
except subprocess.CalledProcessError as error:
	print (f"Error uploading the error.html: {error}")


#Accesible IP address to console
try:
	instance.reload()
	public_ip = instance.public_ip_address
	instance_dns = instance.public_dns_name
	if public_ip:
		print (f"Access the site at: http://{public_ip}")
		print (f"Public DNS for ssh: {instance_dns}")
		print (f"S3 bucket url: {s3_url}")
	else:
		print ("Public IP not available yet")
except Exception as error:
	print (f"Error retrieving public IP: {error}")

#Copying script up to instance
try:
	subprocess.run(["scp","-i",key_path,"monitoring.sh",f"ec2-user@{public_dns}:~"],check=True)
	print ("Copying monitoring script to ec2 instance")
except subprocess.CalledProcessError as error:
	print (f"Error copying monitoring script to ec2 instance: {error}")

#Execute priviledges for script
try:
	subprocess.run(["ssh","-i",key_path,f"ec2-user@{public_dns}","chmod 700 monitoring.sh"],check=True)
	print ("Monitoring script has executable permission")
except subprocess.CalledProcessError as error:
	print (f"Error changing permissions of monitoring script: {error}")

#Monitoring script execution
try:
	subprocess.run(["ssh","-i",key_path,f"ec2-user@{public_dns}","./monitoring.sh"],check=True)
	print ("Running monitoring script")
except subprocess.CalledProcessError as error:
	print (f"Error running monitoring script: {error}")

