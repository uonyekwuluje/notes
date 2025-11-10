from troposphere import Template, Ref, Tags, GetAtt, Output, Export, Sub, ImportValue, Base64, Join
from troposphere import ec2, route53
from troposphere.route53 import RecordSetType
import boto3
from botocore.exceptions import ClientError
from infrastructure import return_vpc_component_ids

# Create a new AWS cloudFormation template
t = Template()

cfn_template = boto3.client('cloudformation')


# Dict for build components
INSTANCE_BUILD_ITEMS = {
    "keypair": "abs-key",
    "ubuntu22id": "ami-005fc0f236362e99f",
    "ubuntu24id": "ami-0e2c8caa4b6378d8c",
    "baseinstancetype": "m3.medium",
}

# Instance Class Count
INSTANCE_TIER_COUNT = {
    "bastion": 1,
    "appserver": 1,
}

# DNS Information and Suffix 
dns_name = "multilabs"
public_dns_name = "pubs.com"
public_dns_id = "847RTR5SC3"


# Check Stack Status
def stack_exists(stack_name, required_status):
    try:
        response = cfn_template.describe_stacks(
            StackName=stack_name
        )
    except ClientError:
        return False
    return response['Stacks'][0]['StackStatus'] == required_status


# Create or update stack
def create_update_security_group_template(vpc_name, stack_name):
    required_status = "CREATE_COMPLETE"
    if stack_exists(stack_name, required_status):
        print(f"{stack_name} Exists. Updating Now")
        generate_sg_cfn_template(vpc_name, stack_name, stack_action="update")
    else:
        print(f"{stack_name} Does Not Exist. Creating Now")
        generate_sg_cfn_template(vpc_name, stack_name, stack_action="create")



# Create Security Groups
def generate_sg_cfn_template(vpc_name, stack_name, stack_action):
    try:
        print("Creating Security Groups")

        # Create Bastion Security Group (AWS::EC2::SecurityGroup)
        bastion_sg_cfn = ec2.SecurityGroup('BastionSecurityGroup')
        bastion_sg_cfn.GroupDescription = "Bastion Security Group"
        bastion_sg_cfn.VpcId = return_vpc_component_ids.get_vpc_id(vpc_name)
        bastion_sg_cfn.Tags = Tags(Name=f"{vpc_name}-Bastion-SecurityGroup")

        # Create Bastion Security Group Ingress (AWS::EC2::SecurityGroupIngress)
        bastion_sg_ingress_cfn = ec2.SecurityGroupIngress('BastionSecurityGroupIngress',
              Description="Bastion SG Ingress", IpProtocol="tcp", FromPort=22, 
              ToPort=22,CidrIp="0.0.0.0/0", GroupId=Ref(bastion_sg_cfn)
        )
    
        # Create MongoDB Security Group (AWS::EC2::SecurityGroup)
        mongodb_sg_cfn = ec2.SecurityGroup('MongoDBSecurityGroup')
        mongodb_sg_cfn.GroupDescription = "MongoDB Security Group"
        mongodb_sg_cfn.VpcId = return_vpc_component_ids.get_vpc_id(vpc_name)
        mongodb_sg_cfn.Tags = Tags(Name=f"{vpc_name}-MongoDB-SecurityGroup")

        # Create MongoDB Security Group Ingress (AWS::EC2::SecurityGroupIngress)
        mongodb_bastion_sg_ingress_cfn = ec2.SecurityGroupIngress('MongoDBBastionSecurityGroupIngress',
            Description="Mongodb Bastion SG Ingress", IpProtocol="tcp", FromPort=22, 
            ToPort=22,CidrIp="0.0.0.0/0", GroupId=Ref(mongodb_sg_cfn)
        )
 
        mongodb_sg_ingress_cfn = ec2.SecurityGroupIngress('MongoSecurityGroupIngress',
            Description="Mongodb SG Ingress", IpProtocol="tcp", FromPort=27016,
            ToPort=27020,CidrIp="0.0.0.0/0", GroupId=Ref(mongodb_sg_cfn)
        )

        # Output Security Groups
        output_bastion_sg_id = Output('outputBastionSG', Value=Ref(bastion_sg_cfn), Export=Export('Infrastructure-BastionSg'))
        output_mongodb_sg_id = Output('outputMongodbSG', Value=Ref(mongodb_sg_cfn), Export=Export('Infrastructure-MongodbSg'))

        # ================================== #
        # Add objects to template            #
        # ================================== # 
        t.add_resource(bastion_sg_cfn)
        t.add_resource(bastion_sg_ingress_cfn)
        t.add_resource(mongodb_sg_cfn)
        t.add_resource(mongodb_bastion_sg_ingress_cfn)
        t.add_resource(mongodb_sg_ingress_cfn)
        t.add_output(output_bastion_sg_id)
        t.add_output(output_mongodb_sg_id)
 
        # Print Cloudformation Template
        print(t.to_yaml())

        if stack_action == "create":
            print(f"Creating {stack_name} stack")
            cfn_template.create_stack(
                StackName=stack_name,
                TemplateBody=t.to_yaml()
            )
            waiter = cfn_template.get_waiter("stack_create_complete")
            waiter.wait(
                StackName=stack_name
            )
            print(f"{stack_name} stack creation complete")
        elif stack_action == "update":
            print(f"Updating {stack_name} stack")
            cfn_template.update_stack(
                StackName=stack_name,
                TemplateBody=t.to_yaml()
            )
            waiter = cfn_template.get_waiter("stack_update_complete")
            waiter.wait(
                StackName=stack_name
            )
            print(f"{stack_name} stack update complete")
    except Exception as e:
        print(f"An error occurred: {e}")





# Create or update ec2 instance stack
def create_update_instance_template(vpc_name, stack_name, instance_type):
    required_status = "CREATE_COMPLETE"
    if stack_exists(stack_name, required_status):
        print(f"{stack_name} Exists. Updating Now")
        generate_instance_cfn_template(vpc_name, stack_name, instance_type, stack_action="update")
    else:
        print(f"{stack_name} Does Not Exist. Creating Now")
        generate_instance_cfn_template(vpc_name, stack_name, instance_type, stack_action="create")


# Generate EC2 Template and create stack
def generate_instance_cfn_template(vpc_name, stack_name, instance_type, stack_action):
    try:
        if instance_type == "bastion":
            security_group_id = ImportValue('Infrastructure-BastionSg')
        else:
            security_group_id = ImportValue('Infrastructure-MongodbSg') 
  
        route53_zone_id = ImportValue('infrastructure-privateHostedZoneId') 
        for instance_count in range(INSTANCE_TIER_COUNT[instance_type]):
            print(f"VPC Name => {vpc_name}")
            print(f"VPC ID   => {return_vpc_component_ids.get_vpc_id(vpc_name)}")
            print(f"Instance Name => {instance_type}{instance_count}")
            print(f"Instance FQDN => {instance_type}{instance_count}.{vpc_name}.{dns_name}")
            print(f"Instance Type => {instance_type}")
            print(f"Instance Count => {INSTANCE_TIER_COUNT[instance_type]}")
            print(f"Subnet ID     => {return_vpc_component_ids.get_subnet_id(vpc_name, 'publicsubnet1')}")
            print(f"Instance Keypair => {INSTANCE_BUILD_ITEMS['keypair']}")
            print(f"Ubuntu 22 AMI ID => {INSTANCE_BUILD_ITEMS['ubuntu22id']}")
            print(f"Ubuntu 24 AMI ID => {INSTANCE_BUILD_ITEMS['ubuntu24id']}")
            print(f"Instance Size    => {INSTANCE_BUILD_ITEMS['baseinstancetype']}")
            print(f"Instance Security Group => {security_group_id}")
            print(f"Private Hosted Zone ID  => {route53_zone_id}")
            print("\n")

            serverName = f"{instance_type}{instance_count}"
            instance = ec2.Instance(
                serverName,
                ImageId=f"{INSTANCE_BUILD_ITEMS['ubuntu22id']}",
                UserData=Base64(Join('', [
                  "#!/bin/bash\n"
                  "sudo hostnamectl set-hostname ",serverName,"\n"
                ])),
                InstanceType=f"{INSTANCE_BUILD_ITEMS['baseinstancetype']}",
                KeyName=f"{INSTANCE_BUILD_ITEMS['keypair']}",
                SecurityGroupIds=[security_group_id],
                SubnetId=f"{return_vpc_component_ids.get_subnet_id(vpc_name, 'publicsubnet1')}",
                Tags=Tags(
                  Name=serverName,
                  Environment=vpc_name,
                ),
            )
            t.add_resource(instance)

            # Set Private DNS 
            instance_record = RecordSetType(
               f"{serverName}PrivateDNSRecord",
               HostedZoneName=Join("", [vpc_name,".", dns_name, "."]),
               Comment=f"DNS name for {serverName}.",
               Name=Join(
                    "", [serverName, ".", vpc_name, ".", dns_name, "."]
               ),
               Type="A",
               TTL="900",
               ResourceRecords=[GetAtt(serverName, "PrivateIp")],
            ) 
            t.add_resource(instance_record)

            # Set public DNS 
            if instance_type == "bastion":
                public_instance_record = RecordSetType(
                   f"{serverName}PublicDNSRecord",
                   HostedZoneName=Join("", [public_dns_name, "."]),
                   Comment=f"Public DNS name for {serverName}.",
                   Name=Join(
                        "", [serverName, ".", public_dns_name, "."]
                   ),
                   Type="A",
                   TTL="900",
                   ResourceRecords=[GetAtt(serverName, "PublicIp")],
                )
                t.add_resource(public_instance_record)


        # Print Cloudformation Template
        print(t.to_yaml())

        if stack_action == "create":
            print(f"Creating {stack_name} stack")
            cfn_template.create_stack(
                StackName=stack_name,
                TemplateBody=t.to_yaml()
            )
            waiter = cfn_template.get_waiter("stack_create_complete")
            waiter.wait(
                StackName=stack_name
            )
            print(f"{stack_name} stack creation complete")
        elif stack_action == "update":
            print(f"Updating {stack_name} stack")
            cfn_template.update_stack(
                StackName=stack_name,
                TemplateBody=t.to_yaml()
            )
            waiter = cfn_template.get_waiter("stack_update_complete")
            waiter.wait(
                StackName=stack_name
            )
            print(f"{stack_name} stack update complete")
    except Exception as e:
        print(f"An error occurred: {e}")
