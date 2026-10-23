"""Who a report or a folder is open to, and in which role.

A grant names one grantee: an exact email, or `EVERYONE` — every email Cloudflare
Access verified. `EVERYONE` is a value of its own type and is stored in a field of
its own, never as a key among the emails, so no address can ever alias it.
Resolution takes an email that `identity.AccessIdentity` already verified: an
unauthenticated request is refused before any grant is consulted.
"""

from enum import Enum, StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    READER = "reader"
    COMMENTER = "commenter"


STRENGTH = {Role.READER: 1, Role.COMMENTER: 2}


def strongest(roles: list[Role | None]) -> Role | None:
    granted = [role for role in roles if role is not None]
    return max(granted, key=STRENGTH.__getitem__, default=None)


class Everyone(Enum):
    """Every verified email, as a grantee."""

    EVERYONE = "everyone"


EVERYONE = Everyone.EVERYONE
Grantee = str | Everyone


class Grants(BaseModel):
    """The grants of one report or one folder."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    emails: dict[str, Role]
    everyone: Role | None

    def role(self, verified_email: str) -> Role | None:
        return strongest([self.emails.get(verified_email), self.everyone])

    def granting(self, grantee: Grantee, role: Role | None) -> "Grants":
        """These grants with `grantee` set to `role`, or revoked when `role` is None."""
        if grantee is EVERYONE:
            return Grants(emails=self.emails, everyone=role)
        emails = {
            email: held for email, held in self.emails.items() if email != grantee
        }
        if role is not None:
            emails[grantee] = role
        return Grants(emails=emails, everyone=self.everyone)

    @property
    def empty(self) -> bool:
        return not self.emails and self.everyone is None


NO_GRANTS = Grants(emails={}, everyone=None)
