"""Config flow for Ostrom integration."""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ARBEITSPREIS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ZIP_CODE,
    DOMAIN,
    URI_AUTH,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_CLIENT_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_ZIP_CODE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_ARBEITSPREIS, default=30.0): vol.Coerce(float),
    }
)


async def _validate_credentials(client_id: str, client_secret: str) -> str | None:
    """Try to authenticate using client_credentials grant. Returns access token or None."""
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with asyncio.timeout(10):
            resp = await session.post(
                URI_AUTH,
                data="grant_type=client_credentials",
                headers=headers,
            )
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token")
            text = await resp.text()
            _LOGGER.debug("Auth failed (%s): %s", resp.status, text)
            return None


class OstromConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ostrom."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            client_secret = user_input[CONF_CLIENT_SECRET].strip()
            zip_code = user_input[CONF_ZIP_CODE].strip()
            arbeitspreis = user_input[CONF_ARBEITSPREIS]

            try:
                token = await _validate_credentials(client_id, client_secret)
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Ostrom auth")
                errors["base"] = "unknown"
            else:
                if not token:
                    errors["base"] = "invalid_auth"
                else:
                    await self.async_set_unique_id(client_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Ostrom ({zip_code})",
                        data={
                            CONF_CLIENT_ID: client_id,
                            CONF_CLIENT_SECRET: client_secret,
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
