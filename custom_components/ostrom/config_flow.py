"""Config flow for Ostrom integration."""
from __future__ import annotations

import base64
import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ARBEITSPREIS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ZIP_CODE,
    DOMAIN,
    URI_AUTH,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_ZIP_CODE): str,
        vol.Required(CONF_ARBEITSPREIS, default=30.0): vol.Coerce(float),
    }
)


async def _validate_credentials(
    client_id: str, client_secret: str, username: str, password: str
) -> str | None:
    """
    Try to authenticate using password grant (for fetching own customer data).
    Returns the access token on success, None on failure.
    """
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    body = (
        f"grant_type=password"
        f"&username={aiohttp.helpers.quote(username)}"
        f"&password={aiohttp.helpers.quote(password)}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                URI_AUTH,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            )
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token")
            text = await resp.text()
            _LOGGER.debug("Auth failed (%s): %s", resp.status, text)
            return None
    except aiohttp.ClientError as err:
        _LOGGER.debug("Auth connection error: %s", err)
        return None


class OstromConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ostrom."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            client_secret = user_input[CONF_CLIENT_SECRET].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            zip_code = user_input[CONF_ZIP_CODE].strip()
            arbeitspreis = user_input[CONF_ARBEITSPREIS]

            token = await _validate_credentials(client_id, client_secret, username, password)
            if not token:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(username.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Ostrom ({zip_code})",
                    data={
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_SECRET: client_secret,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_ZIP_CODE: zip_code,
                        CONF_ARBEITSPREIS: arbeitspreis,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "portal_url": "https://developer.ostrom-api.io/"
            },
        )
