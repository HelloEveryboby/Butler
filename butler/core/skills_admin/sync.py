import json


def sync():
    """返回局域网同步状态（原 skill_local_sync 行为）。"""
    return {"status": "active", "peers": ["Android-Phone-01", "MacBook-Pro"]}


def main():
    print(json.dumps(sync()))


if __name__ == "__main__":
    main()
