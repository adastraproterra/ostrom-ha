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
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ARBEITSPREIS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENVIRONMENT,
    CONF_ZIP_CODE,
    DOMAIN,
    ENV_PRODUCTION,
    ENV_SANDBOX,
    URI_AUTH,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENVIRONMENT, default=ENV_PRODUCTION): SelectSelector(
            SelectSelectorConfig(
                options=[ENV_PRODUCTION, ENV_SANDBOX],
                mode=SelectSelectorMode.LIST,
                translation_key="environment",
            )
        ),
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


async def _validate_credentials(
    client_id: str, client_secret: str, environment: str
) -> tuple[str | None, str | None]:
    """Try client_credentials grant. Returns (token, error_detail)."""
    auth_url = URI_AUTH[environment]
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with asyncio.timeout(10):
            resp = await session.post(
                auth_url,
                data="grant_type=client_credentials",
                headers=headers,
            )
            text = await resp.text()
            _LOGGER.debug(
                "Auth response [%s] %s -> %s", environment, resp.status, text
            )
            if resp.status == 200:
                import json
                data = json.loads(text)
                return data.get("access_token"), None
            return None, f"HTTP {resp.status}: {text}"


class OstromConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ostrom."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {
            "portal_url": "https://developer.ostrom-api.io/",
            "error_detail": "",
        }

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            client_secret = user_input[CONF_CLIENT_SECRET].strip()
            zip_code = user_input[CONF_ZIP_CODE].strip()
            arbeitspreis = user_input[CONF_ARBEITSPREIS]
            environment = user_input[CONF_ENVIRONMENT]

            try:
                token, error_detail = await _validate_credentials(
                    client_id, client_secret, environment
                )
            except (aiohttp.ClientError, TimeoutError) as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Connection error: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected error during Ostrom auth")
                errors["base"] = "unknown"
            else:
                if not token:
                    errors["base"] = "invalid_auth"
                    description_placeholders["error_detail"] = error_detail or ""
                    _LOGGER.error("Ostrom auth failed: %s", error_detail)
                else:
                    await self.async_set_unique_id(f"{environment}_{client_id}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Ostrom ({zip_code})",
                        data={
                            CONF_CLIENT_ID: client_id,
                            CONF_CLIENT_SECRET: client_secret,
                            CONF_ZIP_CODE: zip_code,
                            CONF_ARBEITSPREIS: arbeitspreis,
                            CONF_ENVIRONMENT: environment,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )
