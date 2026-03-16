resource "okta_user" "service-account-1" {
  first_name = "Service"
  last_name  = "Account 1"
  login      = "service1@example.com"
  email      = "service1@example.com"
}
