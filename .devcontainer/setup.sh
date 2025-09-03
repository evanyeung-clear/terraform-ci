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

# update TF_WORKSPACE env when changing directories
# update_tf_workspace() {
#   # Get the first subdirectory after $CODESPACE_VSCODE_FOLDER in $PWD
#   local base="${CODESPACE_VSCODE_FOLDER:-/workspaces/terraform-ci}"
#   local rel="${PWD#$base/}"
#   export TF_WORKSPACE="${rel%%/*}"
# }
# PROMPT_COMMAND="update_tf_workspace; $PROMPT_COMMAND"
# export PROMPT_COMMAND

# print help
echo "Use TF_WORKSPACE=(production|preview) terraform (plan|apply) --var-file=terraform.tfvars.json"