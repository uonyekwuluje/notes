#!/usr/bin/env python3
import click
from enum import Enum
from functools import lru_cache
from copy import copy
import sys
import yaml
from tabulate import tabulate
import boto3

from troposphere import Template, GetAtt
from troposphere import route53
from troposphere import ec2

from infrastructure import create_vpc, infra_instances




@click.group(invoke_without_command=True, chain=True)
def cli():
    pass


# Delete Stacks
@cli.command()
@click.option('-v', '--vpc_name', required=True,
              help="The VPC Name")
@click.option('-r', '--region', default='us-east-1',
              help="AWS VPC Region")
def delete_stack(vpc_name, region):
    stack_names = [f"{vpc_name}-bastion-stack", f"{vpc_name}-mongodb-sg-stack", f"{vpc_name}-stack"]
    cf_resource = boto3.resource('cloudformation', region_name=region)
    for current_stack in stack_names:
        print(f'Deleting stack, {current_stack} in region, {region}')

        # Delete the stack
        stack = cf_resource.Stack(current_stack)
        stack.delete()

        # Wait for stack deletion to complete
        waiter = boto3.client('cloudformation').get_waiter('stack_delete_complete')
        waiter.wait(StackName=current_stack)

        print(f"Stack {current_stack} deleted successfully from region {region}")



# Create VPC Stack
@cli.command()
@click.option('-v', '--vpc_name', default='dev',
              help="The VPC Name")
@click.option('-h', '--hostedzone_name', default='multilabs',
              help="The VPC Hosted Zone")
@click.option('-r', '--region', default='us-east-1',
              help="AWS VPC Region")
def create_update_vpc_stack(vpc_name, region, hostedzone_name):
    stack_name = f"{vpc_name}-stack"
    create_vpc.create_update_cfn_template(vpc_name, region, hostedzone_name, stack_name)


# Create Security Groups
@cli.command()
@click.option('-v', '--vpc_name', default='dev',
              help="The VPC Name")
def create_security_group_stack(vpc_name):
    stack_name = f"{vpc_name}-mongodb-sg-stack"
    infra_instances.create_update_security_group_template(vpc_name, stack_name)


# Create Instances
@cli.command()
@click.option('-i', '--instance_type', default='bastion',
              help="VPC Instance Type")
@click.option('-v', '--vpc_name', default='dev',
              help="The VPC Name")
def create_instance_stack(vpc_name, instance_type):
    stack_name = f"{vpc_name}-{instance_type}-stack"
    infra_instances.create_update_instance_template(vpc_name, stack_name, instance_type)




if __name__ == '__main__':
    cli()
