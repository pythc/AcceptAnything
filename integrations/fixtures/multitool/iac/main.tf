resource "aws_s3_bucket" "example" {
  bucket = "acceptance-integration-fixture-never-created"
  acl = "public-read"
}
