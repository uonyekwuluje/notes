import boto3

client = boto3.client('ec2')

def get_vpc_id(vpc_name):
    """ Get VPC ID """
    response = client.describe_vpcs(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [
                    vpc_name,
                ]
            }
        ]
    )
    resp = response['Vpcs']
    if resp:
        return resp[0]['VpcId']
    else:
       return f"vpc {vpc_name} not found"

def get_subnet_id(vpc_name, subnet_name):
    """ Get Subnet ID """
    subnet_name = f"{vpc_name}-{subnet_name}"
    response = client.describe_subnets(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [
                    subnet_name,
                ]
            }
        ]
    )
    resp_val = response['Subnets'][0]['SubnetId']
    if resp_val:
       return resp_val 
    else:
       return f"{subnet_name} not found"

