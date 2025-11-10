# Create Stack
-----------------------------------------
./build_infra_cli.py create-update-vpc-stack

# Create Security Group Stack
-----------------------------------------
./build_infra_cli.py create-security-group-stack

# Create Instance Stacks
-----------------------------------------
./build_infra_cli.py create-instance-stack
./build_infra_cli.py create-instance-stack -i database -v stg

# Delete Stack
-----------------------------------------
./build_infra_cli.py delete-stack -v dev
