variable "okta_org_name" {
  description = "Okta organization name"
  type        = string
}

variable "okta_base_url" {
  description = "Okta base URL"
  type        = string
  default     = "okta.com"
}

variable "okta_api_client_id" {
  description = "Okta API client ID"
  type        = string
}

variable "okta_api_private_key_id" {
  description = "Okta API private key ID"
  type        = string
}

variable "okta_api_private_key" {
  description = "Okta API private key in PEM format"
  type        = string
  sensitive   = true
}

variable "okta_api_scopes" {
  description = "Okta API scopes"
  type        = list(string)
}
