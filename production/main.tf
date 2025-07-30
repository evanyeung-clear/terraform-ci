terraform {
  required_version = ">= 1.8.2"
  cloud {}

  required_providers {
    okta = {
      source  = "okta/okta"
      version = "~> 4.19.0"
    }
  }
}

provider "okta" {
  org_name       = var.okta_org_name
  base_url       = var.okta_base_url
  client_id      = var.okta_api_client_id
  private_key_id = var.okta_api_private_key_id
  private_key    = var.okta_api_private_key
  scopes         = var.okta_api_scopes
}
