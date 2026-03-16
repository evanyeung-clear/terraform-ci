# scripts
uv is used to manage Python dependencies.

## Terraform State Visualizer
Parses a Terraform state file and generates an interactive network graph in `tfstate-visualizer/`.

Supports both `terraform show -json` and `terraform state pull` output formats.

```
uv run scripts/tfstate_graph_parser.py <path_to_tfstate> [output_dir]
```

Example:
```
terraform show -json > show.json
uv run scripts/tfstate_graph_parser.py show.json
```

Or with `terraform state pull`:
```
terraform state pull > state.json
uv run scripts/tfstate_graph_parser.py state.json
```

Then open `scripts/tfstate-visualizer/index.html` directly in a browser.

## Sailpoint
Sailpoint coverage is calculated by comparing the number of groups in Okta to the number of groups in Sailpoint. The script `sailpoint_coverage.py` is used to calculate this coverage.

```
uv run --env-file .env sailpoint_coverage.py
```

The following environment variables are required:
- SAIL_BASE_URL
- SAIL_CLIENT_ID
- SAIL_CLIENT_SECRET
