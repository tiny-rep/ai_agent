import json
import os
from typing import Any, Type

import requests
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from internal.lib.helper import add_attribute


class GaoDeWeatherArgSchema(BaseModel):
    city: str = Field(description="获取天气的城市名称")


class GaoDeWeatherTool(BaseTool):
    name: str = "gaode_weather_tool"
    description: str = "高德天气获取"
    args_schema: Type[BaseModel] = GaoDeWeatherArgSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        try:
            # 1. 获取APIKEY
            api_key = os.getenv("GAODE_API_KEY")
            if not api_key:
                return "高德的APIKEY未设置"
            # 2. 获取city参数
            city = kwargs.get("city", "")
            api_domain = "https://restapi.amap.com/v3"
            session = requests.session()
            # 3. 根据city参数，获取对应程序的adcode
            city_response = session.request(
                method="GET",
                url=f"{api_domain}/config/district?key={api_key}&keywords={city}",
                headers={"Content-Type": "appliction/json; charset=utf-8"}
            )
            city_response.raise_for_status()
            city_data = city_response.json()
            if city_data.get("info") == "OK":
                ad_code = city_data["districts"][0]["adcode"]
                # 4. 根据adcode 获取天气信息
                weather_response = session.request(
                    method="GET",
                    url=f"{api_domain}/weather/weatherInfo?key={api_key}&city={ad_code}&extensions=all",
                    headers={"Content-Type": "appliction/json; charset=utf-8"}
                )
                weather_response.raise_for_status()
                weather_data = weather_response.json()
                if weather_data.get("info") == "OK":
                    return json.dumps(weather_data)
                return f"获取{city}的天气失败"
        except Exception as e:
            return f"获取{kwargs.get('city', '')}天所失败 {e}"


@add_attribute("args_schema", GaoDeWeatherArgSchema)
def gaode_weather(**kwargs) -> BaseTool:
    return GaoDeWeatherTool()
