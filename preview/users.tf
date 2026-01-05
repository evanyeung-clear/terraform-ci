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

resource "okta_user" "test3" {
  first_name = "John"
  last_name  = "Smith"
  login      = "example3@example.com"
  email      = "example3@example.com"
}

resource "okta_user" "test4" {
  first_name = "John"
  last_name  = "Smith"
  login      = "example4@example.com"
  email      = "example4@example.com"
}


resource "okta_user" "test" {
  for_each = tomap({
    test4       = "example4@example.com"
  })

  first_name = "John"
  last_name  = "Smith"
  login      = each.value
  email      = each.value
}

