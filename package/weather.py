"""
天气预报工具。通过爬取中国天气网提供指定城市的天气信息。
"""
import requests
from bs4 import BeautifulSoup

def get_weather_from_web(city):
    # 定义目标网页的URL，假设使用一个实际的天气API或网页
    url = f"https://weather.cma.cn/api/city/{city}"
    
    try:
        # 发送HTTP请求并获取网页内容
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 提取所需的天气信息
        temperature = soup.find('span', class_='CurrentConditions--tempValue--3KcTQ').text
        description = soup.find('div', class_='CurrentConditions--phraseValue--2xXSr').text
        humidity = soup.find('span', attrs={"data-testid": "PercentageValue"}).text
        wind = soup.find('span', class_='Wind--windWrapper--3Ly7c').text
        
        weather_info = {
            "temperature": temperature,  # 摄氏温度
            "description": description,  # 天气描述
            "humidity": humidity,        # 湿度
            "wind": wind                 # 风速和风向
        }
        
        return weather_info

    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except AttributeError as e:
        print(f"解析天气数据错误: {e}")
        return None

def run(city=None, **kwargs):
    """
    运行天气预报工具。
    :param city: 城市名称或代码。
    """
    if not city:
        city = input("请输入城市名称或代码: ")

    print(f"正在查询 {city} 的天气...")
    weather = get_weather_from_web(city)
    if weather:
        result = (f"{city}当前天气：\n"
                  f"温度：{weather['temperature']}\n"
                  f"状况：{weather['description']}\n"
                  f"湿度：{weather['humidity']}\n"
                  f"风力：{weather['wind']}")
        print(result)
        return result
    else:
        print("无法获取天气信息。")
        return "无法获取天气信息。"
