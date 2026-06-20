import redis
import os

def get_redis_client():
    """
    创建并返回一个 Redis 客户端。
    连接参数取自环境变量，并带有默认值。
    """
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    try:
        # decode_responses=True 使客户端返回字符串而不是字节。
        client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        client.ping() # 检查连接是否可用
        return client
    except redis.exceptions.ConnectionError as e:
        print(f"无法连接到 Redis: {e}")
        return None

# 用于整个应用程序的全局客户端实例。
# 这避免了每次都创建一个新连接。
redis_client = get_redis_client()
