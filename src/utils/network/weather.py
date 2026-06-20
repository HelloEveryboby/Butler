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
