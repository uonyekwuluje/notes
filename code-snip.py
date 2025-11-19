def subnet_creation_association(
    tp,
    vpc_id,
    environment,
    subnet_configs,
    route_table_id
):      
    subnets = {}
    associations = {}
        
    for cfg in subnet_configs:
        name = cfg["name"]
   
        subnet = tp.add_resource( 
            ec2.Subnet(
                name,
                VpcId = vpc_id,
                CidrBlock = cfg["cidr"],
                AvailabilityZone = cfg.get("az"),
                Tags = [ 
                    {"Key": "Name", "Value": f"{environment}-{name}"},
                    {"Key": "subnet_type", "Value": cfg["subnet_type"]}
                ]
            )
        )

        subnets[name] = subnet
        
        assoc = tp.add_resource(
           ec2.SubnetRouteTableAssociation(
               cfg["route_table"], 
               SubnetId = Ref(subnet),
               RouteTableId = route_table_id
           )
        )        
        
        associations[name] = assoc
        
        #return {
        #    "subnets": subnets,
        #    "associations": associations
        #}
        
        


        # Public Subnet Maps
        subnet_configs = [
            {"name": "PublicWebSubnet1b", "cidr": f"{NETWORK_OCTETS[vpc_name]}.0.0/24", "az": "us-east-1b", "subnet_type": "public_web",
             "route_table": "PublicRouteTableAssociationWeb1b"},
            {"name": "PublicWebSubnet1d", "cidr": f"{NETWORK_OCTETS[vpc_name]}.1.0/24", "az": "us-east-1d", "subnet_type": "public_web",
             "route_table": "PublicRouteTableAssociationWeb1d"},
            {"name": "PublicWebSubnet1c", "cidr": f"{NETWORK_OCTETS[vpc_name]}.2.0/24", "az": "us-east-1c", "subnet_type": "public_web",
             "route_table": "PublicRouteTableAssociationWeb1c"},
            {"name": "PublicSvcSubnet1b", "cidr": f"{NETWORK_OCTETS[vpc_name]}.10.0/24", "az": "us-east-1b", "subnet_type": "public_svc",
             "route_table": "PublicRouteTableAssociationSvc1b"},
            {"name": "PublicSvcSubnet1d", "cidr": f"{NETWORK_OCTETS[vpc_name]}.11.0/24", "az": "us-east-1d", "subnet_type": "public_svc",
             "route_table": "PublicRouteTableAssociationSvc1d"},
            {"name": "PublicSvcSubnet1c", "cidr": f"{NETWORK_OCTETS[vpc_name]}.12.0/24", "az": "us-east-1c", "subnet_type": "public_svc",
             "route_table": "PublicRouteTableAssociationSvc1c"}
        ]

        subnet_creation_association(
            t,
            vpc_id = Ref(vpc_cfn),
            environment = vpc_name,
            subnet_configs = subnet_configs,
            route_table_id = Ref(vpc_public_routetable_cfn),
        )


