"""Explicit deployment configuration for the hosted report service."""

import json
import os

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    bucket: str
    database: str
    access_issuer: str
    access_audience: str
    owner_emails: set[str]
    public_origin: str
    port: int = Field(ge=1, le=65535)

    @field_validator("access_issuer")
    @classmethod
    def validate_issuer(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"https://[a-z0-9-]+\.cloudflareaccess\.com", value):
            raise ValueError("Expected an HTTPS Cloudflare Access team origin")
        return value

    @field_validator("public_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or not parts.netloc
            or parts.path
            or parts.query
            or parts.fragment
        ):
            raise ValueError("Expected an HTTPS origin without path")
        return value

    @field_validator("owner_emails")
    @classmethod
    def validate_owners(cls, values: set[str]) -> set[str]:
        if not values or any("@" not in value for value in values):
            raise ValueError("At least one explicit owner email is required")
        return {value.strip().lower() for value in values}


def from_environment() -> Settings:
    return Settings(
        project_id=os.environ["GCP_PROJECT_ID"],
        bucket=os.environ["ARTEFACTS_BUCKET"],
        database=os.environ["ARTEFACTS_DATABASE"],
        access_issuer=os.environ["CLOUDFLARE_ACCESS_ISSUER"],
        access_audience=os.environ["CLOUDFLARE_ACCESS_AUDIENCE"],
        owner_emails=json.loads(os.environ["ARTEFACTS_OWNER_EMAILS"]),
        public_origin=os.environ["ARTEFACTS_PUBLIC_ORIGIN"],
        port=int(os.environ["PORT"]),
    )
