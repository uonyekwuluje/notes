from enum import Enum
from troposphere import Template, Ref, Tags, GetAtt, Output, Export, Sub
from troposphere import ec2, route53
import boto3
import json
from botocore.exceptions import ClientError

# Enum for VPC CIDR Octet
NETWORK_OCTETS = {
    "dev": "192.168",
    "stage": "10.22",
    "prod": "10.23",
}

# Create a new AWS cloudFormation template
t = Template()

cfn_template = boto3.client('cloudformation')





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
def create_update_cfn_template(vpc_name, region, hostedzone_name, stack_name):
    required_status = "CREATE_COMPLETE"
    if stack_exists(stack_name, required_status):
        print(f"{stack_name} Exists. Updating Now")
        generate_cfn_template(vpc_name, region, hostedzone_name, stack_name, stack_action="update")
    else:
        print(f"{stack_name} Does Not Exist. Creating Now")
        generate_cfn_template(vpc_name, region, hostedzone_name, stack_name, stack_action="create")



# Generate stack and perform action
def generate_cfn_template(vpc_name, region, hostedzone_name, stack_name, stack_action):
    try:
        # Get Basic IDs
        ref_stack_id = Ref("AWS::StackId")
        ref_region = Ref("AWS::Region")
        ref_stack_name = Ref("AWS::StackName")

        # Create a VPC (AWS::EC2::VPC)
        vpc_cfn = ec2.VPC('VPC')
        vpc_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.0.0/16"
        vpc_cfn.EnableDnsSupport = True
        vpc_cfn.EnableDnsHostnames = True
        vpc_cfn.Tags = Tags(Name=vpc_name,Department="devops")

        # Create the InternetGateway (AWS::EC2::InternetGateway)
        vpc_igw_cfn = ec2.InternetGateway('InternetGateway')
        vpc_igw_cfn.Tags = Tags(Name=f"{vpc_name}-igw")

        # Create the VPCGatewayAttachment (AWS::EC2::VPCGatewayAttachment)
        vpc_gtwattachement_cfn = ec2.VPCGatewayAttachment('VPCGatewayAttachment')
        vpc_gtwattachement_cfn.VpcId = Ref(vpc_cfn)
        vpc_gtwattachement_cfn.InternetGatewayId= Ref(vpc_igw_cfn)

        # Create Public Routetable (AWS::EC2::RouteTable)
        vpc_public_routetable_cfn = ec2.RouteTable('PublicRouteTable')
        vpc_public_routetable_cfn.VpcId = Ref(vpc_cfn)
        vpc_public_routetable_cfn.Tags = Tags(Name=f"{vpc_name}-publicroutetable",Department="devops")

        # Create Public Route (AWS::EC2::Route)
        vpc_public_route_cfn = ec2.Route('PublicRoute')
        vpc_public_route_cfn.DependsOn = "VPCGatewayAttachment"
        vpc_public_route_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_public_route_cfn.DestinationCidrBlock = "0.0.0.0/0"
        vpc_public_route_cfn.GatewayId = Ref(vpc_igw_cfn)
    
        # Create Public Subnet One (AWS::EC2::Subnet)
        vpc_pub_subnet1_cfn = ec2.Subnet('PublicSubnet1')
        vpc_pub_subnet1_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet1_cfn.AvailabilityZone = "us-east-1a"
        vpc_pub_subnet1_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet1_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.11.0/24" 
        vpc_pub_subnet1_cfn.Tags = Tags(Name=f"{vpc_name}-publicsubnet1",Department="devops")

        # Create Public Subnet Two (AWS::EC2::Subnet)
        vpc_pub_subnet2_cfn = ec2.Subnet('PublicSubnet2')
        vpc_pub_subnet2_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet2_cfn.AvailabilityZone = "us-east-1b"
        vpc_pub_subnet2_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet2_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.12.0/24" 
        vpc_pub_subnet2_cfn.Tags = Tags(Name=f"{vpc_name}-publicsubnet2",Department="devops")

        # Create Public Subnet Three (AWS::EC2::Subnet)
        vpc_pub_subnet3_cfn = ec2.Subnet('PublicSubnet3')
        vpc_pub_subnet3_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet3_cfn.AvailabilityZone = "us-east-1d"
        vpc_pub_subnet3_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet3_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.13.0/24" 
        vpc_pub_subnet3_cfn.Tags = Tags(Name=f"{vpc_name}-publicsubnet3",Department="devops")

        # Create Public Subnet One RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_pub_subnet1_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PublicSubnet1RouteTableAssociation')
        vpc_pub_subnet1_routetable_association_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_pub_subnet1_routetable_association_cfn.SubnetId = Ref(vpc_pub_subnet1_cfn)

        # Create Public Subnet Two RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_pub_subnet2_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PublicSubnet2RouteTableAssociation')
        vpc_pub_subnet2_routetable_association_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_pub_subnet2_routetable_association_cfn.SubnetId = Ref(vpc_pub_subnet2_cfn)

        # Create Public Subnet Three RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_pub_subnet3_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PublicSubnet3RouteTableAssociation')
        vpc_pub_subnet3_routetable_association_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_pub_subnet3_routetable_association_cfn.SubnetId = Ref(vpc_pub_subnet3_cfn)

        # Create EIP for NatGateway (AWS::EC2::EIP)
        vpc_eip_natgateway_cfn = ec2.EIP('EIPforNatGateway')
        vpc_eip_natgateway_cfn.DependsOn = "VPCGatewayAttachment" 
        vpc_eip_natgateway_cfn.Domain = "vpc"
        vpc_eip_natgateway_cfn.Tags = Tags(Name=f"{vpc_name}-EIPNatGateway")

        # Create Nat Gateway (AWS::EC2::NatGateway)
        vpc_natgateway_cfn = ec2.NatGateway('NatGateway')
        vpc_natgateway_cfn.AllocationId = GetAtt(vpc_eip_natgateway_cfn, 'AllocationId')
        vpc_natgateway_cfn.SubnetId = Ref(vpc_pub_subnet1_cfn)
        vpc_natgateway_cfn.Tags = Tags(Name=f"{vpc_name}-NatGateway")

        # Create Private Routetable (AWS::EC2::RouteTable)
        vpc_private_routetable_cfn = ec2.RouteTable('PrivateRouteTable')
        vpc_private_routetable_cfn.VpcId = Ref(vpc_cfn)
        vpc_private_routetable_cfn.Tags = Tags(Name=f"{vpc_name}-privateroutetable")

        # Create Private Route (AWS::EC2::Route)
        vpc_private_route_cfn = ec2.Route('PrivateRoute')
        vpc_private_route_cfn.DependsOn = "VPCGatewayAttachment"
        vpc_private_route_cfn.RouteTableId = Ref(vpc_private_routetable_cfn)
        vpc_private_route_cfn.DestinationCidrBlock = "0.0.0.0/0"
        vpc_private_route_cfn.NatGatewayId = Ref(vpc_natgateway_cfn)

        # Create Private Subnet One (AWS::EC2::Subnet)
        vpc_priv_subnet1_cfn = ec2.Subnet('PrivateSubnet1')
        vpc_priv_subnet1_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet1_cfn.AvailabilityZone = "us-east-1a"
        vpc_priv_subnet1_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet1_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.14.0/24"
        vpc_priv_subnet1_cfn.Tags = Tags(Name=f"{vpc_name}-privatesubnet1")

        # Create Private Subnet Two (AWS::EC2::Subnet)
        vpc_priv_subnet2_cfn = ec2.Subnet('PrivateSubnet2')
        vpc_priv_subnet2_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet2_cfn.AvailabilityZone = "us-east-1b"
        vpc_priv_subnet2_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet2_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.15.0/24"
        vpc_priv_subnet2_cfn.Tags = Tags(Name=f"{vpc_name}-privatesubnet2")

        # Create Private Subnet Three (AWS::EC2::Subnet)
        vpc_priv_subnet3_cfn = ec2.Subnet('PrivateSubnet3')
        vpc_priv_subnet3_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet3_cfn.AvailabilityZone = "us-east-1d"
        vpc_priv_subnet3_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet3_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.16.0/24"
        vpc_priv_subnet3_cfn.Tags = Tags(Name=f"{vpc_name}-privatesubnet3")

        # Create Private Subnet One RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_priv_subnet1_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PrivateSubnet1RouteTableAssociation')
        vpc_priv_subnet1_routetable_association_cfn.RouteTableId = Ref(vpc_private_routetable_cfn)
        vpc_priv_subnet1_routetable_association_cfn.SubnetId = Ref(vpc_priv_subnet1_cfn)

        # Create Private Subnet Two RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_priv_subnet2_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PrivateSubnet2RouteTableAssociation')
        vpc_priv_subnet2_routetable_association_cfn.RouteTableId = Ref(vpc_private_routetable_cfn)
        vpc_priv_subnet2_routetable_association_cfn.SubnetId = Ref(vpc_priv_subnet2_cfn)

        # Create Private Subnet Three RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_priv_subnet3_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PrivateSubnet3RouteTableAssociation')
        vpc_priv_subnet3_routetable_association_cfn.RouteTableId = Ref(vpc_private_routetable_cfn)
        vpc_priv_subnet3_routetable_association_cfn.SubnetId = Ref(vpc_priv_subnet3_cfn)

        # Create Private Hosted Zone (AWS::Route53::HostedZone)
        vpc_private_hostedzone_cfn = route53.HostedZone('PrivateHostedZone')
        vpc_private_hostedzone_cfn.Name = f"{vpc_name}.{hostedzone_name}"
        vpc_private_hostedzone_cfn.HostedZoneConfig = route53.HostedZoneConfiguration(Comment=f"Private Hosted Zone for [{vpc_name}.{hostedzone_name}]")
        vpc_private_hostedzone_cfn.HostedZoneTags = Tags(Name=f"{vpc_name}.{hostedzone_name}")
        vpc_private_hostedzone_cfn.VPCs = [route53.HostedZoneVPCs(VPCId=Ref(vpc_cfn), VPCRegion=Ref("AWS::Region"))]

        # OutPuts
        #output_vpc_id = Output('outputVPC', Value=Ref(vpc_cfn),Export=Export(Sub('${AWS::StackName}-' + 'vpcid')))
        #output_public_subnet1_id = Output('outputPublicSubnet1', Value=Ref(vpc_pub_subnet1_cfn),Export=Export(Sub('${AWS::StackName}-' + 'publicSubnet1Id')))
        #output_public_subnet2_id = Output('outputPublicSubnet2', Value=Ref(vpc_pub_subnet2_cfn),Export=Export(Sub('${AWS::StackName}-' + 'publicSubnet2Id')))
        #output_public_subnet3_id = Output('outputPublicSubnet3', Value=Ref(vpc_pub_subnet3_cfn),Export=Export(Sub('${AWS::StackName}-' + 'publicSubnet3Id')))
        #output_private_subnet1_id = Output('outputPrivateSubnet1', Value=Ref(vpc_priv_subnet1_cfn),Export=Export(Sub('${AWS::StackName}-' + 'privateSubnet1Id')))
        #output_private_subnet2_id = Output('outputPrivateSubnet2', Value=Ref(vpc_priv_subnet2_cfn),Export=Export(Sub('${AWS::StackName}-' + 'privateSubnet2Id')))
        #output_private_subnet3_id = Output('outputPrivateSubnet3', Value=Ref(vpc_priv_subnet3_cfn),Export=Export(Sub('${AWS::StackName}-' + 'privateSubnet3Id')))
        #output_hostedzone_id = Output('outputHostedzoneId', Value=Ref(vpc_private_hostedzone_cfn),Export=Export(Sub('${AWS::StackName}-' + 'privateHostedZoneId')))
        output_vpc_id = Output('outputVPC', Value=Ref(vpc_cfn),Export=Export('infrastructure-vpcid'))
        output_public_subnet1_id = Output('outputPublicSubnet1', Value=Ref(vpc_pub_subnet1_cfn),Export=Export('infrastructure-publicSubnet1Id'))
        output_public_subnet2_id = Output('outputPublicSubnet2', Value=Ref(vpc_pub_subnet2_cfn),Export=Export('infrastructure-publicSubnet2Id'))
        output_public_subnet3_id = Output('outputPublicSubnet3', Value=Ref(vpc_pub_subnet3_cfn),Export=Export('infrastructure-publicSubnet3Id'))
        output_private_subnet1_id = Output('outputPrivateSubnet1', Value=Ref(vpc_priv_subnet1_cfn),Export=Export('infrastructure-privateSubnet1Id'))
        output_private_subnet2_id = Output('outputPrivateSubnet2', Value=Ref(vpc_priv_subnet2_cfn),Export=Export('infrastructure-privateSubnet2Id'))
        output_private_subnet3_id = Output('outputPrivateSubnet3', Value=Ref(vpc_priv_subnet3_cfn),Export=Export('infrastructure-privateSubnet3Id'))
        output_hostedzone_id = Output('outputHostedzoneId', Value=Ref(vpc_private_hostedzone_cfn),Export=Export('infrastructure-privateHostedZoneId'))



        # ================================== #
        # Add the VPC object to the template #
        # ================================== # 
        t.add_resource(vpc_cfn)
        t.add_resource(vpc_igw_cfn)
        t.add_resource(vpc_gtwattachement_cfn)
        t.add_resource(vpc_public_routetable_cfn)
        t.add_resource(vpc_public_route_cfn)
        t.add_resource(vpc_pub_subnet1_cfn)
        t.add_resource(vpc_pub_subnet2_cfn)
        t.add_resource(vpc_pub_subnet3_cfn)
        t.add_resource(vpc_pub_subnet1_routetable_association_cfn)
        t.add_resource(vpc_pub_subnet2_routetable_association_cfn)
        t.add_resource(vpc_pub_subnet3_routetable_association_cfn)
        t.add_resource(vpc_eip_natgateway_cfn)
        t.add_resource(vpc_natgateway_cfn)
        t.add_resource(vpc_private_routetable_cfn)
        t.add_resource(vpc_private_route_cfn)
        t.add_resource(vpc_priv_subnet1_cfn)
        t.add_resource(vpc_priv_subnet2_cfn)
        t.add_resource(vpc_priv_subnet3_cfn)
        t.add_resource(vpc_priv_subnet1_routetable_association_cfn)
        t.add_resource(vpc_priv_subnet2_routetable_association_cfn)
        t.add_resource(vpc_priv_subnet3_routetable_association_cfn)
        t.add_resource(vpc_private_hostedzone_cfn)
        t.add_output(output_vpc_id)
        t.add_output(output_public_subnet1_id)
        t.add_output(output_public_subnet2_id)
        t.add_output(output_public_subnet3_id)
        t.add_output(output_private_subnet1_id)
        t.add_output(output_private_subnet2_id)
        t.add_output(output_private_subnet3_id)
        t.add_output(output_hostedzone_id)

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
