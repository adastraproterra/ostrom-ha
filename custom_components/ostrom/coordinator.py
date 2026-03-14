"""DataUpdateCoordinator for the Ostrom integration."""
from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    ENV_PRODUCTION,
    UPDATE_INTERVAL_MINUTES,
    URI_AUTH,
    URI_API,
)

_LOGGER = logging.getLogger(__name__)


class OstromCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Ostrom data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
        zip_code: str,
        arbeitspreis: float,
        environment: str = ENV_PRODUCTION,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._client_id = client_id
        self._client_secret = client_secret
        self._zip_code = zip_code
        self.arbeitspreis = arbeitspreis
        self._environment = environment
        self._auth_url = URI_AUTH[environment]
        self._api_url = URI_API[environment]
        self._contract_id: str | None = None

    async def _get_token(self) -> str:
        """Fetch OAuth2 access token using client_credentials grant."""
        encoded = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(10):
                resp = await session.post(
                    self._auth_url,
                    data="grant_type=client_credentials",
                    headers=headers,
                )
                text = await resp.text()
                _LOGGER.debug("Token response [%s]: %s", resp.status, text)
                if resp.status != 200:
                    raise UpdateFailed(f"Auth failed ({resp.status}): {text}")
                import json
                return json.loads(text)["access_token"]

    async def _get_contract_id(self, token: str) -> str | None:
        """Fetch the contract ID via GET /contracts."""
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(10):
                resp = await session.get(
                    f"{self._api_url}/contracts", headers=headers
                )
                text = await resp.text()
                _LOGGER.debug("Contracts response [%s]: %s", resp.status, text)
                if resp.status != 200:
                    _LOGGER.warning("Could not fetch contracts (%s): %s", resp.status, text)
                    return None
                import json
                data = json.loads(text)
                contracts = data if isinstance(data, list) else data.get("data", [])
                if contracts:
                    c = contracts[0]
                    cid = c.get("id") or c.get("contractId")
                    _LOGGER.debug("Using contract ID: %s", cid)
                    return str(cid)
                return None

    async def _get_spot_prices(self, token: str) -> list[dict]:
        """Fetch day-ahead spot prices (resolution HOUR only per API docs)."""
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=2)
        params = {
            "startDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "resolution": "HOUR",
            "zip": self._zip_code,
        }
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(10):
                resp = await session.get(
                    f"{self._api_url}/spot-prices", headers=headers, params=params
                )
                if resp.status != 200:
                    text = await resp.text()
                    raise UpdateFailed(f"Spot prices failed ({resp.status}): {text}")
                import json
                raw = json.loads(await resp.text())
                return raw.get("data", raw) if isinstance(raw, dict) else raw

    async def _get_consumption(self, token: str, contract_id: str) -> dict:
        """Fetch consumption. Allowed resolutions: HOUR, DAY, MONTH."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        result: dict = {"monthly_kwh": None, "daily_kwh": None, "total_cost": None}

        async with aiohttp.ClientSession() as session:
            for resolution, start, key_kwh in [
                ("MONTH", month_start, "monthly_kwh"),
                ("DAY", day_start, "daily_kwh"),
            ]:
                params = {
                    "startDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "endDate": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "resolution": resolution,
                }
                async with asyncio.timeout(10):
                    resp = await session.get(
                        f"{self._api_url}/contracts/{contract_id}/energy-consumption",
                        headers=headers,
                        params=params,
                    )
                    if resp.status == 200:
                        import json
                        data = json.loads(await resp.text())
                        entries = (
                            data.get("data", data) if isinstance(data, dict) else data
                        )
                        if entries:
                            result[key_kwh] = round(
                                sum(
                                    e.get("consumptionKwh", e.get("consumption", 0) or 0)
                                    for e in entries
                                ),
                                3,
                            )
                            if resolution == "MONTH":
                                result["total_cost"] = round(
                                    sum(
                                        e.get("costGross", e.get("cost", 0) or 0)
                                        for e in entries
                                    ),
                                    2,
                                )
                    else:
                        _LOGGER.debug(
                            "Consumption (%s) not available: %s", resolution, resp.status
                        )
        return result

    async def _async_update_data(self) -> dict:
        """Fetch all data from the Ostrom API."""
        try:
            token = await self._get_token()

            if self._contract_id is None:
                self._contract_id = await self._get_contract_id(token)

            spot_prices = await self._get_spot_prices(token)

            now = datetime.now(timezone.utc)
            current_price_eur: float | None = None
            forecast: list[dict] = []

            for entry in spot_prices:
                try:
                    dt = datetime.fromisoformat(
                        entry.get("date", "").replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                    price_gross = entry.get("grossKwhPrice") or entry.get("netKwhPrice")
                    if price_gross is not None:
                        price_eur = round(price_gross / 100, 4)
                        forecast.append({
                            "datetime": dt.isoformat(),
                            "price_eur_kwh": price_eur,
                            "price_ct_kwh": round(price_gross, 4),
                        })
                        if dt.replace(minute=0, second=0, microsecond=0) == now.replace(
                            minute=0, second=0, microsecond=0
                        ):
                            current_price_eur = price_eur
                except (ValueError, TypeError) as err:
                    _LOGGER.debug("Could not parse price entry %s: %s", entry, err)

            consumption: dict = {"monthly_kwh": None, "daily_kwh": None, "total_cost": None}
            if self._contract_id:
                consumption = await self._get_consumption(token, self._contract_id)

            return {
                "current_price_eur": current_price_eur,
                "forecast": forecast,
                "monthly_kwh": consumption["monthly_kwh"],
                "daily_kwh": consumption["daily_kwh"],
                "total_cost": consumption["total_cost"],
                "arbeitspreis": self.arbeitspreis,
            }

        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Network error: {err}") from err
