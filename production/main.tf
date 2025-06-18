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
}
