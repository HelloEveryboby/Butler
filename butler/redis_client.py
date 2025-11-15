import redis
import os

def get_redis_client():
    """
    Creates and returns a Redis client.
    Connection parameters are taken from environment variables with defaults.
    """
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    try:
        # decode_responses=True makes the client return strings instead of bytes.
        client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        client.ping() # Check if the connection is alive
        return client
    except redis.exceptions.ConnectionError as e:
        print(f"Could not connect to Redis: {e}")
        return None

# Global client instance to be used throughout the application.
# This avoids creating a new connection every time.
redis_client = get_redis_client()
