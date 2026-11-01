"""Email, through Amazon SES (adr/Accounts: AWS only).

Off until `PASHU_EMAIL_FROM` names a sender SES has verified. Until then
`enabled()` is false, the site says resets go through a company admin, and
nothing pretends an email was sent. In SES's sandbox only verified recipients
receive mail; production access lifts that, and is requested in the SES console.
"""

from __future__ import annotations

import logging

from .config import get_settings


def enabled() -> bool:
    return bool(get_settings().email_from)


def send(to: str, subject: str, text: str) -> bool:
    """Sends one plain-text email. False, logged, when SES refuses or is not set up; never raises."""
    settings = get_settings()
    if not settings.email_from:
        return False
    try:
        import boto3

        boto3.client("sesv2", region_name=settings.aws_region).send_email(
            FromEmailAddress=settings.email_from,
            Destination={"ToAddresses": [to]},
            Content={"Simple": {"Subject": {"Data": subject}, "Body": {"Text": {"Data": text}}}},
        )
        return True
    except Exception:  # noqa: BLE001 - a failed email must not fail the request that asked for it
        logging.getLogger(__name__).warning("SES did not send an account email")
        return False
