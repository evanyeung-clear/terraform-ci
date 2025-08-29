#! /bin/bash

# if SOPS_AGE_KEY is not present exit
if [ -z "$SOPS_AGE_KEY" ]; then
  echo "SOPS_AGE_KEY is not set"
  exit 1
fi

# initialize Terraform where there is a main.tf
find "/workspaces/terraform-ci" -name 'main.tf' -execdir bash -c 'TF_WORKSPACE=$(basename "$(pwd)") terraform init' \;

# decrypt any terraform.enc.tfvars.json
find "/workspaces/terraform-ci" -name 'terraform.enc.tfvars.json' -execdir bash -c 'sops -d --output terraform.tfvars.json terraform.enc.tfvars.json' \;

# print help
echo "Use TF_WORKSPACE=(production|preview) terraform (plan|apply) --var-file=terraform.tfvars.json"