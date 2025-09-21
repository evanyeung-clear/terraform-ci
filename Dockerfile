FROM ghcr.io/astral-sh/uv:python3.13-alpine

# Install Terraform
ARG TERRAFORM_VERSION=1.8.3
RUN apk add --no-cache curl unzip \
    && curl -fsSL https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform.zip \
    && apk del curl unzip

# Copy the project into the image
COPY /src /src

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /src
RUN uv sync --locked

# Make terraform.py executable and available
# RUN chmod +x /src/terraform.py
# ENV PATH="/app/src:$PATH"

# WORKDIR /workspace

ENTRYPOINT [ "uv", "run", "--script", "/src/terraform.py" ]
# ENTRYPOINT [ "terraform" ]
