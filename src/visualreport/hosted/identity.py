"""Cloudflare-signed identities, independent of the request's origin path."""

from dataclasses import dataclass
from typing import Protocol

import jwt
from fastapi import HTTPException


class SigningKeys(Protocol):
    def get_signing_key_from_jwt(self, token: str): ...


@dataclass(frozen=True)
class AccessIdentity:
    issuer: str
    audience: str
    keys: SigningKeys

    def email(self, token: str | None) -> str:
        if not token:
            raise HTTPException(401, "Cloudflare Access authentication required")
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "email"]},
            )
            email = claims["email"]
            if (
                not isinstance(email, str)
                or "@" not in email
                or claims.get("type") != "app"
            ):
                raise ValueError("Expected an authenticated Access application user")
            return email.strip().lower()
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
            raise HTTPException(401, "Invalid Cloudflare Access identity") from error


def access_identity(issuer: str, audience: str) -> AccessIdentity:
    return AccessIdentity(
        issuer, audience, jwt.PyJWKClient(f"{issuer}/cdn-cgi/access/certs", timeout=5)
    )
