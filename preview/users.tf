resource "okta_user" "test1" {
  first_name = "John"
  last_name  = "Smith"
  login      = "example@example.com"
  email      = "example@example.com"
}

resource "okta_user" "test2" {
  first_name = "John"
  last_name  = "Smith"
  login      = "example2@example.com"
  email      = "example2@example.com"
}

