FROM python:3.13-alpine

ARG TERRAFORM_VERSION=1.8.3

# Install Terraform
RUN apk add --no-cache curl unzip \
    && curl -fsSL https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform.zip \
    && apk del curl unzip

# Copy the Terraform wrapper into the image
COPY /src/terraform.py /terraform.py

ENTRYPOINT [ "python", "/terraform.py" ]
