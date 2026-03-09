"""DataUpdateCoordinator for the Ostrom integration."""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone

import aiohttp
import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_MINUTES, URI_AUTH, URI_API

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
    ) -> None:
        """Initialize coordinator."""
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
        self._access_token: str | None = None
        self._contract_id: str | None = None

    async def _get_token(self) -> str:
        """Fetch OAuth2 access token using client credentials."""
        credentials = f"{self._client_id}:{self._client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with async_timeout.timeout(10):
                resp = await session.post(
                    URI_AUTH,
                    data="grant_type=client_credentials",
                    headers=headers,
                )
                if resp.status != 200:
                    text = await resp.text()
                    raise UpdateFailed(f"Auth failed ({resp.status}): {text}")
                data = await resp.json()
                return data["access_token"]

    async def _get_contract_id(self, token: str) -> str | None:
        """Fetch the contract ID from the API."""
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with async_timeout.timeout(10):
                resp = await session.get(
                    f"{URI_API}/contracts", headers=headers
                )
                if resp.status != 200:
                    _LOGGER.warning(
                        "Could not fetch contract ID (%s)", resp.status
                    )
                    return None
                data = await resp.json()
                # data can be a list or dict with a list
                contracts = data if isinstance(data, list) else data.get("data", [])
                if contracts:
                    return str(contracts[0].get("id") or contracts[0].get("contractId"))
                return None

    async def _get_spot_prices(self, token: str) -> list[dict]:
        """Fetch spot prices for today and tomorrow."""
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
            async with async_timeout.timeout(10):
                resp = await session.get(
                    f"{URI_API}/spot-prices", headers=headers, params=params
                )
                if resp.status != 200:
                    text = await resp.text()
                    raise UpdateFailed(
                        f"Spot prices failed ({resp.status}): {text}"
                    )
                raw = await resp.json()
                return raw.get("data", raw) if isinstance(raw, dict) else raw

    async def _get_consumption(self, token: str, contract_id: str) -> dict:
        """Fetch monthly and daily consumption."""
        now = datetime.now(timezone.utc)

        # Monthly: current month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = now

        # Daily: today
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = now

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        result = {"monthly_kwh": None, "daily_kwh": None, "total_cost": None}

        async with aiohttp.ClientSession() as session:
            # Monthly
            params = {
                "startDate": month_start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "endDate": month_end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "resolution": "MONTH",
            }
            async with async_timeout.timeout(10):
                resp = await session.get(
                    f"{URI_API}/contracts/{contract_id}/energy-consumption",
                    headers=headers,
                    params=params,
                )
                if resp.status == 200:
                    data = await resp.json()
                    entries = data.get("data", data) if isinstance(data, dict) else data
                    if entries:
                        total = sum(
                            e.get("consumptionKwh", e.get("consumption", 0) or 0)
                            for e in entries
                        )
                        result["monthly_kwh"] = round(total, 3)
                        cost = sum(
                            e.get("costGross", e.get("cost", 0) or 0)
                            for e in entries
                        )
                        result["total_cost"] = round(cost, 2)
                else:
                    _LOGGER.debug("Monthly consumption not available: %s", resp.status)

            # Daily
            params["startDate"] = day_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            params["endDate"] = day_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            params["resolution"] = "DAY"
            async with async_timeout.timeout(10):
                resp = await session.get(
                    f"{URI_API}/contracts/{contract_id}/energy-consumption",
                    headers=headers,
                    params=params,
                )
                if resp.status == 200:
                    data = await resp.json()
                    entries = data.get("data", data) if isinstance(data, dict) else data
                    if entries:
                        total = sum(
                            e.get("consumptionKwh", e.get("consumption", 0) or 0)
                            for e in entries
                        )
                        result["daily_kwh"] = round(total, 3)
                else:
                    _LOGGER.debug("Daily consumption not available: %s", resp.status)

        return result

    async def _async_update_data(self) -> dict:
        """Fetch all data from the Ostrom API."""
        try:
            token = await self._get_token()
            self._access_token = token

            # Get contract ID once (cache it)
            if self._contract_id is None:
                self._contract_id = await self._get_contract_id(token)

            spot_prices = await self._get_spot_prices(token)

            # Find current hour price
            now = datetime.now(timezone.utc)
            current_price_eur = None
            forecast = []

            for entry in spot_prices:
                try:
                    dt_str = entry.get("date", "")
                    # Normalize: try parsing with Z suffix
                    dt_str_clean = dt_str.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt_str_clean)
                    dt = dt.astimezone(timezone.utc)

                    price_gross = entry.get("grossKwhPrice")
                    if price_gross is None:
                        price_gross = entry.get("netKwhPrice")
                    if price_gross is not None:
                        price_eur = round(price_gross / 100, 4)  # ct → €
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

            # Consumption data
            consumption = {"monthly_kwh": None, "daily_kwh": None, "total_cost": None}
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

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error: {err}") from err
          
