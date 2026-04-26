# terraform-ci

![Sailpoint coverage](https://raw.githubusercontent.com/evanyeung-clear/terraform-ci/refs/heads/badges/badges/sailpoint-cov.svg)
![Terraform coverage](https://raw.githubusercontent.com/evanyeung-clear/terraform-ci/refs/heads/badges/badges/terraform-cov.svg)
![Owner Coverage](https://raw.githubusercontent.com/evanyeung-clear/terraform-ci/refs/heads/badges/badges/owner-cov.svg)  
<sub>_\* updated nightly_</sub>

[![Latest production deploy](https://raw.githubusercontent.com/evanyeung-clear/terraform-ci/refs/heads/badges/badges/latest-production-branch.svg)](https://github.com/evanyeung-clear/terraform-ci/tree/deploy-production/production) 
[![Latest preview deploy](https://raw.githubusercontent.com/evanyeung-clear/terraform-ci/refs/heads/badges/badges/latest-preview-branch.svg)](https://github.com/evanyeung-clear/terraform-ci/tree/deploy-preview/preview)  
<sub>_\* changes may take a few minutes to appear_</sub>

GitHub Actions + Python tooling for managing Okta resources with Terraform. Changes to `preview/` and `production/` are planned automatically on PR open, and applied on demand via PR comment.

## Usage

```sh
# Apply changes
/terraform apply   # or: /tf apply
```

Comment `/terraform apply` (or `/tf apply`) on an open PR to deploy. The pipeline verifies all status checks have passed and no other deployment is in progress before proceeding.

On Windows, use Docker in WSL:

```sh
docker compose run --rm --env-file ./.env terraform init
```

## CI Pipeline

### Plan (on PR open / push)

1. Decrypts SOPS-encrypted variable files
2. Runs `terraform init`, `fmt`, and `validate`; posts inline review comments on formatting issues
3. Runs a discovery plan (`-refresh=false`) and saves it to a binary plan file, then converts it to JSON via `terraform show -json`
4. **Classifies** the plan — detects creates, updates, deletes, and import operations; builds a `-target=` list scoped only to changed resources
5. Runs a targeted `terraform plan` and posts the output as a PR comment; previous plan/apply comments are collapsed and marked outdated
6. Sets a `terraform-apply` commit status to `pending` with instructions to comment `/terraform apply`
7. Runs a **Trivy** IaC security scan against the changed directory; results are uploaded to the GitHub Security tab
8. **Blocks the PR** if the plan mixes import operations with creates/updates/deletes (see [Mixed imports](#mixed-imports))

If another branch holds the deployment lock, plan runs against a **speculative copy** of the current state so the output is still meaningful.

### Apply (on `/terraform apply` comment)

1. Reacts to the comment with 👀, then checks which directories (`preview/`, `production/`) are modified in the PR
2. Verifies the branch is up to date with the base branch
3. Verifies all required status checks have passed
4. **Acquires a deployment lock** for the target environment — only one deployment runs at a time. If the lock is held by another branch, the apply is blocked and a link to the blocking deployment is posted
5. Freezes the current real state to a `-speculative` workspace (so concurrent plan runs by other PRs remain accurate)
6. Runs a targeted `terraform apply` scoped to only the resources changed in the PR
7. On success: tags the commit as `deploy-<environment>`, adds a PR label, and updates the deployment badge
8. On failure (non-import): **auto-reverts** by re-applying the `main` branch configuration and releasing the lock
9. Posts a detailed apply comment (or updates the in-progress comment) with the console output and resource attribute values

### Deployment lock

The lock prevents concurrent deploys to the same environment. While a lock is held:
- Other PRs targeting the same environment see a blocked apply with a link to the active deployment
- Plan runs for other PRs use the frozen speculative state so their output stays accurate

The lock is released automatically on PR merge or on a successful revert.

### Mixed imports

A PR that mixes `import {}` blocks with creates, updates, or deletes is blocked at plan time. This prevents partial state corruption — imports must be in their own PR.

Exceptions can be declared in `.terraform-ci.yaml` under `mixed_import_allowed` for attributes that are known to differ between import and a fresh create (e.g. provider-defaulted fields):

```yaml
# .terraform-ci.yaml
mixed_import_allowed:
  okta_app_oauth:
    refresh_token_rotation: STATIC
    refresh_token_leeway: 0
```

### Apply comment outputs

The apply comment includes a table of resource attribute values after apply. Which attributes are shown is configured per resource type in `.terraform-ci.yaml`:

```yaml
# .terraform-ci.yaml
outputs:
  okta_user:
    - id
    - login
  okta_group:
    - id
  okta_app_oauth:
    - client_id
```

## Python wrapper (`src/terraform.py`)

`terraform.py` is a cross-platform drop-in wrapper around the `terraform` binary. Run it with `uv run`:

```sh
cd preview
uv run ../src/terraform.py plan -var-file=terraform.tfvars.json
uv run ../src/terraform.py plan-light          # targeted plan (see below)
```

### File consolidation

Terraform does not natively support nested module directories without explicit `module {}` blocks. The wrapper consolidates all `.tf` files found in subdirectories into a single `_consolidated.tf` file in the working directory before running any command, then removes it afterward.

A `_consolidated_source_map.json` is written alongside it mapping line ranges in the consolidated file back to their original source files. CI uses this to report `fmt` errors against the correct file and line number.

### `plan-light`

`plan-light` is a custom command that runs a scoped plan limited to only the resources that have changes:

1. Runs `terraform plan -refresh=false -json` to discover changed resource addresses
2. Re-runs `terraform plan` with `-target=<addr>` for each changed resource

This is faster than a full plan when only a small number of resources are affected.

### Safety

- **Recursion guard**: sets `TERRAFORM_WRAPPER_RUNNING=1` in the environment to prevent accidentally invoking itself
- **Directory validation**: exits early if the current directory does not contain a `.tf` file with a `terraform {}` block
- **Allow-list**: only `init`, `fmt`, `validate`, `plan`, `apply`, `show`, and `plan-light` are accepted
