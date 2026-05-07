import boto3


s3 = boto3.client(
    "s3",
    endpoint_url="https://<ACCOUNT_ID>.r2.cloudflarestorage.com",
    aws_access_key_id="<your_access_key_id>",
    aws_secret_access_key="<your_secret_access_key>",
    region_name="auto",
)

# Test: list buckets
response = s3.list_buckets()
print("Buckets:", [b["Name"] for b in response["Buckets"]])
