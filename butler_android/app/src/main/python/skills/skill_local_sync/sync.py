import sys
import json

def main():
    print(json.dumps({"status": "active", "peers": ["Android-Phone-01", "MacBook-Pro"]}))

if __name__ == "__main__":
    main()
