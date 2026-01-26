# coverage
Code is used to calculate coverage for Sailpoint and Terraform. uv is used to manage Python dependencies.

## Sailpoint
Sailpoint coverage is calculated by comparing the number of groups in Okta to the number of groups in Sailpoint. The script `sailpoint_coverage.py` is used to calculate this coverage.

```
uv run --env-file .env sailpoint_coverage.py
```

The following environment variables are required:
- SAIL_BASE_URL
- SAIL_CLIENT_ID
- SAIL_CLIENT_SECRET
