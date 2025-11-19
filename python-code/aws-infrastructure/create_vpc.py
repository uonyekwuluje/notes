from enum import Enum
from troposphere import Template, Ref, Tags, GetAtt, Output, Export, Sub, Select
from troposphere import ec2, route53
from troposphere.networkfirewall import (
    RuleGroup,
    RuleVariables,
    IPSet,
    ReferenceSets,
    RuleGroup,
    RulesSource,
    StatefulRule,
    Header,
    MatchAttributes,
    PortRange,
    Address,
    RuleGroupProperty, 
    RulesSource, 
    RulesSourceList,
    Firewall,
    FirewallPolicy,
    FirewallPolicyProperty,
    StatefulRuleGroupReference,
    SubnetMapping
)
import boto3
import json
from botocore.exceptions import ClientError
import os

# Enum for VPC CIDR Octet
NETWORK_OCTETS = {
    "stg1": "10.21",
    "stg2": "10.22",
    "stg3": "10.23",
    "stg4": "10.24",
    "stg5": "10.25",
}

FIREWALL_WHITELIST = ['.amazonaws.com',
        '.amazonlinux.com',
        '.cisofy.com',
        '.deb.nodesource.com',
        '.docker.io',
        '.endpoint.ingress.rapid7.com',
        '.fiscloudservices.com',
        '.fnfis.com',
        '.github.com',
        '.github.org',
        '.githubusercontent.com',
        '.googleapis.com',
        '.highcharts.com',
        '.insight.rapid7.com',
        '.jenkins-ci.org',
        '.jenkins.io',
        '.launchpad.net',
        '.letsencrypt.org',
        '.mongodb.com',
        '.mongodb.org',
        '.nodejs.org',
        '.paloaltonetworks.com',
        '.paymentech.net',
        '.percona.com',
        '.python.org',
        '.pnpm.io',
        '.registry.npmjs.org',
        '.repo.maven.apache.org',
        '.rkhunter.sourceforge.net',
        '.salesforce.com',
        '.sentry.io',
        '.slack.com',
        '.snapcraft.io',
        '.ubuntu.com',
        '.hashicorp.com',
        '.wp-digital-users-ppe-digital-default.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-stage-bootstrap.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-stage-bootstrap.apps.eu-west-2-tb1gr.stage.msp.worldpay.io',
        'kafka-payments-bootstrap.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-bootstrap.apps.eu-west-2-tb1gr.stage.msp.worldpay.io',
        'kafka-payments-bootstrap.apps.eu-west-1-i8tjd.prod.msp.worldpay.io',
        'kafka-payments-bootstrap.apps.eu-west-2-bmgat.prod.msp.worldpay.io',
        'kafka-payments-0.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-1.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-2.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-stage-0.apps.eu-west-2-tb1gr.stage.msp.worldpay.io',
        'kafka-payments-stage-1.apps.eu-west-2-tb1gr.stage.msp.worldpay.io',
        'kafka-payments-stage-2.apps.eu-west-2-tb1gr.stage.msp.worldpay.io',
        'kafka-payments-stage-0.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-stage-1.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-stage-2.apps.eu-west-1-hf2js.stage.msp.worldpay.io',
        'kafka-payments-0.apps.eu-west-1-i8tjd.prod.msp.worldpay.io',
        'kafka-payments-1.apps.eu-west-1-i8tjd.prod.msp.worldpay.io',
        'kafka-payments-2.apps.eu-west-1-i8tjd.prod.msp.worldpay.io',
        'kafka-payments-0.apps.eu-west-2-bmgat.prod.msp.worldpay.io',
        'kafka-payments-1.apps.eu-west-2-bmgat.prod.msp.worldpay.io',
        'kafka-payments-2.apps.eu-west-2-bmgat.prod.msp.worldpay.io',
        'kafka-payments-0.apps.eu-west-2-tb1gr.stage.msp.worldpay.io',
        'kafka-payments-1.apps.eu-west-2-tb1gr.stage.msp.worldpay.io',
        'kafka-payments-2.apps.eu-west-2-tb1gr.stage.msp.worldpay.io']




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


# Create and generate tags
def get_stack_tags(vpc_name, stack_name, built_by, build_reason):
    tags_dict = {"environment": vpc_name}
    tags_dict.update({"stack-name": stack_name})

    if built_by is not None:
        tags_dict.update({"built_by": built_by})
    if build_reason is not None:
        tags_dict.update({"build_reason": build_reason})
        
    build_url = os.getenv("BUILD_URL", "Not built on Jenkins")
    tags_dict.update({"jenkins_build_url": build_url})
        
    return tags_dict


# Create or update stack
def create_update_cfn_template(vpc_name, region, hostedzone_name, stack_name, built_by=None, build_reason=None):
    required_status = "CREATE_COMPLETE"
    tags_dict = get_stack_tags(vpc_name, stack_name, built_by, build_reason)

    if stack_exists(stack_name, required_status):
        print(f"{stack_name} Exists. Updating Now")
        generate_cfn_template(vpc_name, region, hostedzone_name, stack_name, stack_action="update", tags_dict=tags_dict)
    else:
        print(f"{stack_name} Does Not Exist. Creating Now")
        generate_cfn_template(vpc_name, region, hostedzone_name, stack_name, stack_action="create", tags_dict=tags_dict)



# Generate stack and perform action
def generate_cfn_template(vpc_name, region, hostedzone_name, stack_name, stack_action, tags_dict):
    try:
        # Get Basic IDs
        ref_stack_id = Ref("AWS::StackId")
        ref_region = Ref("AWS::Region")
        ref_stack_name = Ref("AWS::StackName")

        # Network Firewall Group
        internal_ips = IPSet(
            Definition=[f"{NETWORK_OCTETS[vpc_name]}.0.0/16"]
        )

        firewall_whitelist_cfn = RuleGroup('DomainAllowStatefulRuleGroup')
        firewall_whitelist_cfn.Description = f"{vpc_name}-Firewall-DomainWhitelist"
        firewall_whitelist_cfn.RuleGroupName = f"{vpc_name}-Firewall-DomainWhitelist"
        firewall_whitelist_cfn.Type = "STATEFUL"
        firewall_whitelist_cfn.Capacity = 200
        firewall_whitelist_cfn.RuleGroup = RuleGroupProperty(
           RulesSource = RulesSource(
                RulesSourceList = RulesSourceList(
                    GeneratedRulesType = "ALLOWLIST",
                    TargetTypes = ["HTTP_HOST", "TLS_SNI"],
                    Targets = FIREWALL_WHITELIST
                )
           ),
           RuleVariables = RuleVariables(
               IPSets = {"HOME_NET":  internal_ips}
           )    
        )   
        firewall_whitelist_cfn_tags_dict = tags_dict
        firewall_whitelist_cfn_tags_dict.update({"Name": f"{vpc_name}-Firewall-DomainWhitelist"})
        firewall_whitelist_cfn.Tags = Tags(firewall_whitelist_cfn_tags_dict)


        # Create a VPC (AWS::EC2::VPC)
        vpc_cfn = ec2.VPC('VPC')
        vpc_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.0.0/16"
        vpc_cfn.EnableDnsSupport = True
        vpc_cfn.EnableDnsHostnames = True
        tags_dict.update({"Name": vpc_name})
        vpc_cfn.Tags = Tags(tags_dict)

        # Create the InternetGateway (AWS::EC2::InternetGateway)
        vpc_igw_cfn = ec2.InternetGateway('InternetGateway')
        vpc_igw_cfn_tags_dict = tags_dict
        vpc_igw_cfn_tags_dict.update({"Name": f"{vpc_name}-InternetGateway"})
        vpc_igw_cfn.Tags = Tags(vpc_igw_cfn_tags_dict)

        # Create the VPCGatewayAttachment (AWS::EC2::VPCGatewayAttachment)
        vpc_gtwattachement_cfn = ec2.VPCGatewayAttachment('VPCGatewayAttachment')
        vpc_gtwattachement_cfn.DependsOn = [vpc_cfn.title, vpc_igw_cfn.title]
        vpc_gtwattachement_cfn.VpcId = Ref(vpc_cfn)
        vpc_gtwattachement_cfn.InternetGatewayId= Ref(vpc_igw_cfn)

        # Create Public Routetable (AWS::EC2::RouteTable)
        vpc_public_routetable_cfn = ec2.RouteTable('PublicRouteTable')
        vpc_public_routetable_cfn.VpcId = Ref(vpc_cfn)
        vpc_public_routetable_cfn_tags_dict = tags_dict
        vpc_public_routetable_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicRouteTable"})
        vpc_public_routetable_cfn.Tags = Tags(vpc_public_routetable_cfn_tags_dict)

        # Create Public Route (AWS::EC2::Route)
        vpc_public_route_cfn = ec2.Route('PublicInternetTrafficRoute')
        vpc_public_route_cfn.DependsOn = "VPCGatewayAttachment"
        vpc_public_route_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_public_route_cfn.DestinationCidrBlock = "0.0.0.0/0"
        vpc_public_route_cfn.GatewayId = Ref(vpc_igw_cfn)
    
        # Create Public Subnet One (AWS::EC2::Subnet) PublicWebSubnet1b
        vpc_pub_subnet1_cfn = ec2.Subnet('PublicWebSubnet1b')
        vpc_pub_subnet1_cfn.DependsOn = "VPC"
        vpc_pub_subnet1_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet1_cfn.AvailabilityZone = "us-east-1b"
        #vpc_pub_subnet1_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet1_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.0.0/24"
        vpc_pub_subnet1_cfn_tags_dict = tags_dict
        vpc_pub_subnet1_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicWebSubnet1b", "subnet_type": "public_web"})
        vpc_pub_subnet1_cfn.Tags = Tags(vpc_pub_subnet1_cfn_tags_dict)

        # Create Public Subnet Two (AWS::EC2::Subnet) PublicWebSubnet1d
        vpc_pub_subnet2_cfn = ec2.Subnet('PublicWebSubnet1d')
        vpc_pub_subnet2_cfn.DependsOn = [vpc_cfn.title]
        vpc_pub_subnet2_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet2_cfn.AvailabilityZone = "us-east-1d"
        #vpc_pub_subnet2_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet2_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.1.0/24"
        vpc_pub_subnet2_cfn_tags_dict = tags_dict
        vpc_pub_subnet2_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicWebSubnet1d", "subnet_type": "public_web"})
        vpc_pub_subnet2_cfn.Tags = Tags(vpc_pub_subnet2_cfn_tags_dict)

        # Create Public Subnet Three (AWS::EC2::Subnet) PublicWebSubnet1c
        vpc_pub_subnet3_cfn = ec2.Subnet('PublicWebSubnet1c')
        vpc_pub_subnet3_cfn.DependsOn = [vpc_cfn.title] 
        vpc_pub_subnet3_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet3_cfn.AvailabilityZone = "us-east-1c"
        #vpc_pub_subnet3_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet3_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.2.0/24"
        vpc_pub_subnet3_cfn_tags_dict = tags_dict
        vpc_pub_subnet3_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicWebSubnet1c", "subnet_type": "public_web"})
        vpc_pub_subnet3_cfn.Tags = Tags(vpc_pub_subnet3_cfn_tags_dict)

        # Create Public Subnet Four (AWS::EC2::Subnet) PublicSvcSubnet1b
        vpc_pub_subnet4_cfn = ec2.Subnet('PublicSvcSubnet1b')
        vpc_pub_subnet4_cfn.DependsOn = [vpc_cfn.title] 
        vpc_pub_subnet4_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet4_cfn.AvailabilityZone = "us-east-1b"
        #vpc_pub_subnet4_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet4_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.10.0/24"
        vpc_pub_subnet4_cfn_tags_dict = tags_dict
        vpc_pub_subnet4_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicSvcSubnet1b", "subnet_type": "public_svc"})
        vpc_pub_subnet4_cfn.Tags = Tags(vpc_pub_subnet4_cfn_tags_dict)

        # Create Public Subnet Five (AWS::EC2::Subnet) PublicSvcSubnet1d
        vpc_pub_subnet5_cfn = ec2.Subnet('PublicSvcSubnet1d')
        vpc_pub_subnet5_cfn.DependsOn = [vpc_cfn.title]
        vpc_pub_subnet5_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet5_cfn.AvailabilityZone = "us-east-1d"
        #vpc_pub_subnet5_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet5_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.11.0/24"
        vpc_pub_subnet5_cfn_tags_dict = tags_dict
        vpc_pub_subnet5_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicSvcSubnet1d", "subnet_type": "public_svc"})
        vpc_pub_subnet5_cfn.Tags = Tags(vpc_pub_subnet5_cfn_tags_dict)
        
        # Create Public Subnet Six (AWS::EC2::Subnet) PublicSvcSubnet1c
        vpc_pub_subnet6_cfn = ec2.Subnet('PublicSvcSubnet1c')
        vpc_pub_subnet6_cfn.DependsOn = [vpc_cfn.title]
        vpc_pub_subnet6_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_subnet6_cfn.AvailabilityZone = "us-east-1c"
        #vpc_pub_subnet6_cfn.MapPublicIpOnLaunch = True
        vpc_pub_subnet6_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.12.0/24"
        vpc_pub_subnet6_cfn_tags_dict = tags_dict
        vpc_pub_subnet6_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicSvcSubnet1c", "subnet_type": "public_svc"})
        vpc_pub_subnet6_cfn.Tags = Tags(vpc_pub_subnet6_cfn_tags_dict)



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

        # Create Public Subnet Four RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_pub_subnet4_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PublicSubnet4RouteTableAssociation')
        vpc_pub_subnet4_routetable_association_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_pub_subnet4_routetable_association_cfn.SubnetId = Ref(vpc_pub_subnet4_cfn)

        # Create Public Subnet Five RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_pub_subnet5_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PublicSubnet5RouteTableAssociation')
        vpc_pub_subnet5_routetable_association_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_pub_subnet5_routetable_association_cfn.SubnetId = Ref(vpc_pub_subnet5_cfn)

        # Create Public Subnet Six RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_pub_subnet6_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PublicSubnet6RouteTableAssociation')
        vpc_pub_subnet6_routetable_association_cfn.RouteTableId = Ref(vpc_public_routetable_cfn)
        vpc_pub_subnet6_routetable_association_cfn.SubnetId = Ref(vpc_pub_subnet6_cfn)




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



        # Create Private Subnet One (AWS::EC2::Subnet) PrivateSvcSubnet1b
        vpc_priv_subnet1_cfn = ec2.Subnet('PrivateSvcSubnet1b')
        vpc_priv_subnet1_cfn.DependsOn = [vpc_cfn.title]
        vpc_priv_subnet1_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet1_cfn.AvailabilityZone = "us-east-1b"
        vpc_priv_subnet1_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet1_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.20.0/24"
        vpc_priv_subnet1_cfn_tags_dict = tags_dict
        vpc_priv_subnet1_cfn_tags_dict.update({"Name": f"{vpc_name}-PrivateSvcSubnet1b", "subnet_type": "private_svc"})
        vpc_priv_subnet1_cfn.Tags = Tags(vpc_priv_subnet1_cfn_tags_dict)

        # Create Private Subnet Two (AWS::EC2::Subnet) PrivateSvcSubnet1d
        vpc_priv_subnet2_cfn = ec2.Subnet('PrivateSvcSubnet1d')
        vpc_priv_subnet2_cfn.DependsOn = [vpc_cfn.title]
        vpc_priv_subnet2_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet2_cfn.AvailabilityZone = "us-east-1d"
        vpc_priv_subnet2_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet2_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.21.0/24"
        vpc_priv_subnet2_cfn_tags_dict = tags_dict
        vpc_priv_subnet2_cfn_tags_dict.update({"Name": f"{vpc_name}-PrivateSvcSubnet1d", "subnet_type": "private_svc"})
        vpc_priv_subnet2_cfn.Tags = Tags(vpc_priv_subnet2_cfn_tags_dict)

        # Create Private Subnet Three (AWS::EC2::Subnet) PrivateSvcSubnet1c
        vpc_priv_subnet3_cfn = ec2.Subnet('PrivateSvcSubnet1c')
        vpc_priv_subnet3_cfn.DependsOn = [vpc_cfn.title]
        vpc_priv_subnet3_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet3_cfn.AvailabilityZone = "us-east-1c"
        vpc_priv_subnet3_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet3_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.22.0/24"
        vpc_priv_subnet3_cfn_tags_dict = tags_dict
        vpc_priv_subnet3_cfn_tags_dict.update({"Name": f"{vpc_name}-PrivateSvcSubnet1c", "subnet_type": "private_svc"})
        vpc_priv_subnet3_cfn.Tags = Tags(vpc_priv_subnet3_cfn_tags_dict)

        # Create Private Subnet Four (AWS::EC2::Subnet) PrivateDbSubnet1b
        vpc_priv_subnet4_cfn = ec2.Subnet('PrivateDbSubnet1b')
        vpc_priv_subnet4_cfn.DependsOn = [vpc_cfn.title]
        vpc_priv_subnet4_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet4_cfn.AvailabilityZone = "us-east-1b"
        vpc_priv_subnet4_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet4_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.30.0/24"
        vpc_priv_subnet4_cfn_tags_dict = tags_dict
        vpc_priv_subnet4_cfn_tags_dict.update({"Name": f"{vpc_name}-PrivateDbSubnet1b", "subnet_type": "private_db"})
        vpc_priv_subnet4_cfn.Tags = Tags(vpc_priv_subnet4_cfn_tags_dict)

        # Create Private Subnet Five (AWS::EC2::Subnet) PrivateDbSubnet1d
        vpc_priv_subnet5_cfn = ec2.Subnet('PrivateDbSubnet1d')
        vpc_priv_subnet5_cfn.DependsOn = [vpc_cfn.title]
        vpc_priv_subnet5_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet5_cfn.AvailabilityZone = "us-east-1d"
        vpc_priv_subnet5_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet5_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.31.0/24"
        vpc_priv_subnet5_cfn_tags_dict = tags_dict
        vpc_priv_subnet5_cfn_tags_dict.update({"Name": f"{vpc_name}-PrivateDbSubnet1d", "subnet_type": "private_db"})
        vpc_priv_subnet5_cfn.Tags = Tags(vpc_priv_subnet5_cfn_tags_dict)

        # Create Private Subnet Six (AWS::EC2::Subnet) PrivateDbSubnet1c
        vpc_priv_subnet6_cfn = ec2.Subnet('PrivateDbSubnet1c')
        vpc_priv_subnet6_cfn.DependsOn = [vpc_cfn.title]
        vpc_priv_subnet6_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_subnet6_cfn.AvailabilityZone = "us-east-1c"
        vpc_priv_subnet6_cfn.MapPublicIpOnLaunch = False
        vpc_priv_subnet6_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.32.0/24"
        vpc_priv_subnet6_cfn_tags_dict = tags_dict
        vpc_priv_subnet6_cfn_tags_dict.update({"Name": f"{vpc_name}-PrivateDbSubnet1c", "subnet_type": "private_db"})
        vpc_priv_subnet6_cfn.Tags = Tags(vpc_priv_subnet6_cfn_tags_dict)


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

        # Create Private Subnet Four RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_priv_subnet4_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PrivateSubnet4RouteTableAssociation')
        vpc_priv_subnet4_routetable_association_cfn.RouteTableId = Ref(vpc_private_routetable_cfn)
        vpc_priv_subnet4_routetable_association_cfn.SubnetId = Ref(vpc_priv_subnet4_cfn)

        # Create Private Subnet Five RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_priv_subnet5_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PrivateSubnet5RouteTableAssociation')
        vpc_priv_subnet5_routetable_association_cfn.RouteTableId = Ref(vpc_private_routetable_cfn)
        vpc_priv_subnet5_routetable_association_cfn.SubnetId = Ref(vpc_priv_subnet5_cfn)

        # Create Private Subnet Six RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_priv_subnet6_routetable_association_cfn = ec2.SubnetRouteTableAssociation('PrivateSubnet6RouteTableAssociation')
        vpc_priv_subnet6_routetable_association_cfn.RouteTableId = Ref(vpc_private_routetable_cfn)
        vpc_priv_subnet6_routetable_association_cfn.SubnetId = Ref(vpc_priv_subnet6_cfn)

        # ================================ #
        #  Protected and Firewall Subnets  #
        # ================================ #
        # Create Public Protected Subnet (AWS::EC2::Subnet) PublicProtectedSubnet1c
        vpc_pub_protected_subnet_cfn = ec2.Subnet('PublicProtectedSubnet1c')
        vpc_pub_protected_subnet_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_protected_subnet_cfn.AvailabilityZone = "us-east-1c"
        vpc_pub_protected_subnet_cfn.MapPublicIpOnLaunch = False
        vpc_pub_protected_subnet_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.42.0/24"
        vpc_pub_protected_subnet_cfn_tags_dict = tags_dict
        vpc_pub_protected_subnet_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicProtectedSubnet1c"})
        vpc_pub_protected_subnet_cfn.Tags = Tags(vpc_pub_protected_subnet_cfn_tags_dict)

        # Create Private Protected Subnet (AWS::EC2::Subnet) PrivateProtectedSvcSubnet1c
        vpc_priv_protected_subnet_cfn = ec2.Subnet('PrivateProtectedSvcSubnet1c')
        vpc_priv_protected_subnet_cfn.VpcId = Ref(vpc_cfn)
        vpc_priv_protected_subnet_cfn.AvailabilityZone = "us-east-1c"
        vpc_priv_protected_subnet_cfn.MapPublicIpOnLaunch = False
        vpc_priv_protected_subnet_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.52.0/24"
        vpc_priv_protected_subnet_cfn_tags_dict = tags_dict
        vpc_priv_protected_subnet_cfn_tags_dict.update({"Name": f"{vpc_name}-PrivateProtectedSvcSubnet1c", "subnet_type": "private_protected_svc"})
        vpc_priv_protected_subnet_cfn.Tags = Tags(vpc_priv_protected_subnet_cfn_tags_dict)

        # Create Public Firewall Subnet (AWS::EC2::Subnet) PublicFirewallSubnet1c
        vpc_pub_firewall_subnet_cfn = ec2.Subnet('PublicFirewallSubnet1c')
        vpc_pub_firewall_subnet_cfn.VpcId = Ref(vpc_cfn)
        vpc_pub_firewall_subnet_cfn.AvailabilityZone = "us-east-1c"
        vpc_pub_firewall_subnet_cfn.MapPublicIpOnLaunch = False
        vpc_pub_firewall_subnet_cfn.CidrBlock = f"{NETWORK_OCTETS[vpc_name]}.62.0/24"
        vpc_pub_firewall_subnet_cfn_tags_dict = tags_dict
        vpc_pub_firewall_subnet_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicFirewallSubnet1c", "subnet_type": "firewall_svc"})
        vpc_pub_firewall_subnet_cfn.Tags = Tags(vpc_pub_firewall_subnet_cfn_tags_dict)

        # Create Firewall Routetable (AWS::EC2::RouteTable)
        vpc_public_firewall_routetable_cfn = ec2.RouteTable('FirewallRouteTable1c')
        vpc_public_firewall_routetable_cfn.VpcId = Ref(vpc_cfn)
        vpc_public_firewall_routetable_cfn_tags_dict = tags_dict
        vpc_public_firewall_routetable_cfn_tags_dict.update({"Name": f"{vpc_name}-FirewallRouteTable1c"})
        vpc_public_firewall_routetable_cfn.Tags = Tags(vpc_public_firewall_routetable_cfn_tags_dict)

        # Create Firewall Route (AWS::EC2::Route)
        vpc_public_firewall_route_cfn = ec2.Route('FirewallRoute1c')
        vpc_public_firewall_route_cfn.DependsOn = "VPCGatewayAttachment"
        vpc_public_firewall_route_cfn.RouteTableId = Ref(vpc_public_firewall_routetable_cfn)
        vpc_public_firewall_route_cfn.DestinationCidrBlock = "0.0.0.0/0"
        vpc_public_firewall_route_cfn.GatewayId = Ref(vpc_igw_cfn)

        # Create Firewall RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        vpc_public_firewall_subnet_routetable_association_cfn = ec2.SubnetRouteTableAssociation('FirewallRouteTableAssociation1c')
        vpc_public_firewall_subnet_routetable_association_cfn.RouteTableId = Ref(vpc_public_firewall_routetable_cfn)
        vpc_public_firewall_subnet_routetable_association_cfn.SubnetId = Ref(vpc_pub_firewall_subnet_cfn)

        # Create Network Firewall Policy
        firewall_policy_props = FirewallPolicyProperty(
             StatelessDefaultActions = ["aws:forward_to_sfe"],
             StatelessFragmentDefaultActions = ["aws:forward_to_sfe"],
             StatefulRuleGroupReferences = [
                 StatefulRuleGroupReference(
                     ResourceArn = GetAtt(firewall_whitelist_cfn, 'RuleGroupArn')
                 )
             ]
        )        
        vpc_network_firewall_policy_cfn = FirewallPolicy('VpcEgressFirewallPolicy')
        vpc_network_firewall_policy_cfn.DependsOn = [firewall_whitelist_cfn.title]
        vpc_network_firewall_policy_cfn.Description = f"{vpc_name} Firewall Policy"
        vpc_network_firewall_policy_cfn.FirewallPolicyName = f"{vpc_name}-Firewall-Policy"
        vpc_network_firewall_policy_cfn.FirewallPolicy = firewall_policy_props
        vpc_network_firewall_policy_cfn_tags_dict = tags_dict
        vpc_network_firewall_policy_cfn_tags_dict.update({"Name": f"{vpc_name}-Firewall-Policy"})
        vpc_network_firewall_policy_cfn.Tags = Tags(vpc_network_firewall_policy_cfn_tags_dict)

        # Create Network Firewall
        vpc_network_firewall_cfn = Firewall('VpcFirewall1c')
        vpc_network_firewall_cfn.FirewallName = f"{vpc_name}-VpcFirewall1c"
        vpc_network_firewall_cfn.VpcId = Ref(vpc_cfn)
        vpc_network_firewall_cfn.FirewallPolicyArn = Ref(vpc_network_firewall_policy_cfn)
        vpc_network_firewall_cfn.SubnetMappings = [
             SubnetMapping(SubnetId = Ref(vpc_pub_firewall_subnet_cfn))
        ]        
        vpc_network_firewall_cfn_tags_dict = tags_dict
        vpc_network_firewall_cfn_tags_dict.update({"Name": f"{vpc_name}-Firewall1c"})
        vpc_network_firewall_cfn.Tags = Tags(vpc_network_firewall_cfn_tags_dict)

        # Create Public Protected Routetable (AWS::EC2::RouteTable)
        vpc_public_protected_routetable_cfn = ec2.RouteTable('PublicProtectedRouteTable1c')
        vpc_public_protected_routetable_cfn.DependsOn = [vpc_cfn.title]
        vpc_public_protected_routetable_cfn.VpcId = Ref(vpc_cfn)
        vpc_public_protected_routetable_cfn_tags_dict = tags_dict
        vpc_public_protected_routetable_cfn_tags_dict.update({"Name": f"{vpc_name}-PublicProtectedRouteTable1c"})
        vpc_public_protected_routetable_cfn.Tags = Tags(vpc_public_protected_routetable_cfn_tags_dict)

        # Create Public Protected Route (AWS::EC2::Route)
        vpc_public_protected_route_cfn = ec2.Route('PublicProtectedRoute1c')
        vpc_public_protected_route_cfn.DependsOn = [vpc_network_firewall_cfn]
        vpc_public_protected_route_cfn.RouteTableId = Ref(vpc_public_protected_routetable_cfn)
        vpc_public_protected_route_cfn.DestinationCidrBlock = "0.0.0.0/0"
        #vpc_firewall_endpoint_ids = GetAtt(vpc_network_firewall_cfn, "VpcEndpointIds")
        #vpc_firewall_endpoint_id = Select(0, vpc_firewall_endpoint_ids)
        #vpc_public_protected_route_cfn.VpcEndpointId = vpc_firewall_endpoint_ids[0]
        vpc_public_protected_route_cfn.VpcEndpointId = GetAtt(vpc_network_firewall_cfn, "FirewallEndpointId")
        

        ## Create Firewall RouteTable Association (AWS::EC2::SubnetRouteTableAssociation)
        #vpc_public_firewall_subnet_routetable_association_cfn = ec2.SubnetRouteTableAssociation('FirewallRouteTableAssociation1c')
        #vpc_public_firewall_subnet_routetable_association_cfn.RouteTableId = Ref(vpc_public_firewall_routetable_cfn)
        #vpc_public_firewall_subnet_routetable_association_cfn.SubnetId = Ref(vpc_pub_firewall_subnet_cfn)









        # OutPuts
        output_firewall_whitelist_arn = Output('outputFirewallWhitelistArn', Value=GetAtt(firewall_whitelist_cfn.title, 'RuleGroupArn'))
        output_vpc_id = Output('outputVPC', Value=Ref(vpc_cfn),Export=Export('infrastructure-vpcid'))
        output_public_subnet1_id = Output('outputPublicSubnet1', Value=Ref(vpc_pub_subnet1_cfn))
        output_public_subnet2_id = Output('outputPublicSubnet2', Value=Ref(vpc_pub_subnet2_cfn))
        output_public_subnet3_id = Output('outputPublicSubnet3', Value=Ref(vpc_pub_subnet3_cfn))
        output_public_subnet4_id = Output('outputPublicSubnet4', Value=Ref(vpc_pub_subnet4_cfn))
        output_public_subnet5_id = Output('outputPublicSubnet5', Value=Ref(vpc_pub_subnet5_cfn))
        output_public_subnet6_id = Output('outputPublicSubnet6', Value=Ref(vpc_pub_subnet6_cfn))
        output_private_subnet1_id = Output('outputPrivateSubnet1', Value=Ref(vpc_priv_subnet1_cfn))
        output_private_subnet2_id = Output('outputPrivateSubnet2', Value=Ref(vpc_priv_subnet2_cfn))
        output_private_subnet3_id = Output('outputPrivateSubnet3', Value=Ref(vpc_priv_subnet3_cfn))
        output_private_subnet4_id = Output('outputPrivateSubnet4', Value=Ref(vpc_priv_subnet4_cfn))
        output_private_subnet5_id = Output('outputPrivateSubnet5', Value=Ref(vpc_priv_subnet5_cfn))
        output_private_subnet6_id = Output('outputPrivateSubnet6', Value=Ref(vpc_priv_subnet6_cfn))
        output_public_protected_subnet_id = Output('outputProdProtectedSubnet', Value=Ref(vpc_pub_protected_subnet_cfn))
        output_private_protected_subnet_id = Output('outputPrivateProtectedSubnet', Value=Ref(vpc_priv_protected_subnet_cfn))
        output_public_firewall_subnet_id = Output('outputPublicFirewallSubnet', Value=Ref(vpc_pub_firewall_subnet_cfn))


        # ================================== #
        # Add the VPC object to the template #
        # ================================== #
        t.add_resource(firewall_whitelist_cfn)
        t.add_resource(vpc_network_firewall_policy_cfn)
        t.add_resource(vpc_network_firewall_cfn)
        t.add_resource(vpc_cfn)
        t.add_resource(vpc_igw_cfn)
        t.add_resource(vpc_gtwattachement_cfn)
        t.add_resource(vpc_public_routetable_cfn)
        t.add_resource(vpc_public_route_cfn)
        t.add_resource(vpc_pub_subnet1_cfn)
        t.add_resource(vpc_pub_subnet2_cfn)
        t.add_resource(vpc_pub_subnet3_cfn)
        t.add_resource(vpc_pub_subnet4_cfn)
        t.add_resource(vpc_pub_subnet5_cfn)
        t.add_resource(vpc_pub_subnet6_cfn)
        t.add_resource(vpc_pub_subnet1_routetable_association_cfn)
        t.add_resource(vpc_pub_subnet2_routetable_association_cfn)
        t.add_resource(vpc_pub_subnet3_routetable_association_cfn)
        t.add_resource(vpc_pub_subnet4_routetable_association_cfn)
        t.add_resource(vpc_pub_subnet5_routetable_association_cfn)
        t.add_resource(vpc_pub_subnet6_routetable_association_cfn)
        t.add_resource(vpc_eip_natgateway_cfn)
        t.add_resource(vpc_natgateway_cfn)
        t.add_resource(vpc_private_routetable_cfn)
        t.add_resource(vpc_private_route_cfn)
        t.add_resource(vpc_priv_subnet1_cfn)
        t.add_resource(vpc_priv_subnet2_cfn)
        t.add_resource(vpc_priv_subnet3_cfn)
        t.add_resource(vpc_priv_subnet4_cfn)
        t.add_resource(vpc_priv_subnet5_cfn)
        t.add_resource(vpc_priv_subnet6_cfn)
        t.add_resource(vpc_priv_subnet1_routetable_association_cfn)
        t.add_resource(vpc_priv_subnet2_routetable_association_cfn)
        t.add_resource(vpc_priv_subnet3_routetable_association_cfn)
        t.add_resource(vpc_priv_subnet4_routetable_association_cfn)
        t.add_resource(vpc_priv_subnet5_routetable_association_cfn)
        t.add_resource(vpc_priv_subnet6_routetable_association_cfn)
        t.add_resource(vpc_pub_protected_subnet_cfn)
        t.add_resource(vpc_priv_protected_subnet_cfn)
        t.add_resource(vpc_pub_firewall_subnet_cfn)
        t.add_resource(vpc_public_firewall_routetable_cfn)
        t.add_resource(vpc_public_firewall_route_cfn)
        t.add_resource(vpc_public_firewall_subnet_routetable_association_cfn)
        t.add_resource(vpc_public_protected_routetable_cfn)
        t.add_resource(vpc_public_protected_route_cfn)
        t.add_output(output_vpc_id)
        t.add_output(output_firewall_whitelist_arn)
        t.add_output(output_public_subnet1_id)
        t.add_output(output_public_subnet2_id)
        t.add_output(output_public_subnet3_id)
        t.add_output(output_public_subnet4_id)
        t.add_output(output_public_subnet5_id)
        t.add_output(output_public_subnet6_id)
        t.add_output(output_private_subnet1_id)
        t.add_output(output_private_subnet2_id)
        t.add_output(output_private_subnet3_id)
        t.add_output(output_private_subnet4_id)
        t.add_output(output_private_subnet5_id)
        t.add_output(output_private_subnet6_id)
        t.add_output(output_public_protected_subnet_id)
        t.add_output(output_private_protected_subnet_id)
        t.add_output(output_public_firewall_subnet_id)

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
