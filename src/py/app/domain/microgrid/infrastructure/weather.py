"""Open-Meteo weather adapter with a deterministic offline demo fallback."""

from __future__ import annotations

# ruff: noqa: PLR2004
import math
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx
import pandas as pd


class WeatherAdapter(Protocol):
    """Weather forecast port consumed by the application workflow."""

    async def forecast(self, *, latitude: float, longitude: float, start: datetime, periods: int = 96) -> pd.DataFrame:
        """Return a 15-minute weather frame for the requested horizon."""
        ...


class OpenMeteoWeatherAdapter:
    """Fetch 15-minute weather forecasts for one site."""

    endpoint = "https://api.open-meteo.com/v1/forecast"

    async def forecast(self, *, latitude: float, longitude: float, start: datetime, periods: int = 96) -> pd.DataFrame:
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "minutely_15": "temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m,shortwave_radiation,direct_normal_irradiance,diffuse_radiation",
            "forecast_days": 2,
            "timezone": "Asia/Shanghai",
        }
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(self.endpoint, params=params)
                response.raise_for_status()
            payload = response.json()["minutely_15"]
            frame = pd.DataFrame(
                {
                    "ghi": payload["shortwave_radiation"],
                    "dni": payload["direct_normal_irradiance"],
                    "dhi": payload["diffuse_radiation"],
                    "temp_air": payload["temperature_2m"],
                    "wind_speed": [float(value) / 3.6 for value in payload["wind_speed_10m"]],
                    "relative_humidity": payload["relative_humidity_2m"],
                    "cloud_cover": payload["cloud_cover"],
                },
                index=pd.DatetimeIndex(payload["time"]).tz_localize("Asia/Shanghai"),
            )
            nearest = frame.index.get_indexer([pd.Timestamp(start)], method="nearest")[0]
            return frame.iloc[nearest : nearest + periods]
        except (httpx.HTTPError, KeyError, ValueError, IndexError):
            return demo_weather(start=start, periods=periods)


def demo_weather(*, start: datetime, periods: int = 96) -> pd.DataFrame:
    """Deterministic Taizhou summer profile used when external weather is unavailable."""
    index = pd.date_range(start=start, periods=periods, freq="15min", tz=start.tzinfo or "Asia/Shanghai")
    hours = index.hour + index.minute / 60
    irradiance = [max(0.0, 850 * math.sin(math.pi * (hour - 5.5) / 13.0)) for hour in hours]
    return pd.DataFrame(
        {
            "ghi": irradiance,
            "dni": [value * 0.72 for value in irradiance],
            "dhi": [value * 0.28 for value in irradiance],
            "temp_air": [29 + 5 * math.sin(math.pi * (hour - 8) / 12) for hour in hours],
            "wind_speed": [2.2 + 0.5 * math.sin(math.pi * hour / 12) for hour in hours],
            "relative_humidity": [70 - 12 * math.sin(math.pi * (hour - 6) / 12) for hour in hours],
            "cloud_cover": [32 + 12 * math.sin(math.pi * hour / 9) for hour in hours],
        },
        index=index,
    )


def history_for_training(*, end: datetime, periods: int = 14 * 96) -> tuple[list[datetime], list[float], list[float]]:
    """Generate deterministic training data when measured 15-minute load is absent."""
    start = end - timedelta(minutes=15 * periods)
    index = pd.date_range(start=start, periods=periods, freq="15min", tz=end.tzinfo or "Asia/Shanghai")
    loads: list[float] = []
    temperatures: list[float] = []
    for position, point in enumerate(index):
        hour = point.hour + point.minute / 60
        work = 1.0 if point.dayofweek < 5 else 0.86
        profile = 0.66 + 0.26 * math.sin(math.pi * (hour - 6) / 15) ** 2
        deterministic_noise = 13 * math.sin(position * 0.37)
        loads.append(max(180.0, 540 * work * profile + deterministic_noise))
        temperatures.append(28 + 5 * math.sin(math.pi * (hour - 8) / 12))
    return list(index.to_pydatetime()), loads, temperatures
