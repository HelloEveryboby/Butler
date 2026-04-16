#!/usr/bin/env python3
"""
每日穿搭助手 - 天气获取脚本
用法: python get_weather.py [城市名]
输出: JSON 格式的天气数据
"""
import sys
import json
import urllib.request
import urllib.parse

def get_weather(city):
    """
    获取城市天气数据
    使用 wttr.in 服务（无需 API Key，适用于轻量级调用）
    返回格式化的 JSON 数据
    """
    try:
        # 对中文城市名进行 URL 编码
        city_encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{city_encoded}?format=j1"

        # 设置 User-Agent 以避免被拦截
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

            # 提取关键信息
            current = data['current_condition'][0]
            weather_desc = current['weatherDesc'][0]['value']
            temp_c = current['temp_C']
            feels_like_c = current['FeelsLikeC']
            humidity = current['humidity']
            windspeed_kmph = current['windspeedKmph']

            # 提取今日最高最低温
            today_astronomy = data['weather'][0]
            max_temp = today_astronomy['maxtempC']
            min_temp = today_astronomy['mintempC']

            result = {
                "city": city,
                "status": "success",
                "weather": weather_desc,
                "temperature": {
                    "current": temp_c,
                    "feels_like": feels_like_c,
                    "max": max_temp,
                    "min": min_temp
                },
                "humidity": humidity + "%",
                "wind_speed": windspeed_kmph + "km/h",
                "advice_trigger": ""
            }

            # 添加中文友好提示
            weather_lower = weather_desc.lower()
            if "rain" in weather_lower or "drizzle" in weather_lower:
                result["advice_trigger"] = "雨"
            elif int(windspeed_kmph) > 30:
                result["advice_trigger"] = "大风"

            return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "city": city,
            "status": "error",
            "message": f"天气查询失败，请检查城市名或网络: {str(e)}"
        }, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        city_name = sys.argv[1]
    else:
        city_name = "Beijing"  # 默认城市，可根据需要修改
    print(get_weather(city_name))
