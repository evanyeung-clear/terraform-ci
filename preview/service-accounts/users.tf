resource "okta_user" "service-account-1" {
  first_name = "Service"
  last_name  = "Account 1"
  login      = "service1@example.com"
  email      = "service1@example.com"
}

resource "okta_user" "service-account-1" {
  first_name = "Service"
  last_name  = "Account 2"
  login      = "service2@example.com"
  email      = "service2@example.com"
}
