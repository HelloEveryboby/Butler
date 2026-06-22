import sys
import json

def main():
    print(json.dumps({"status": "monitoring", "sources": ["GitHub Releases", "V2EX - Creative"]}))

if __name__ == "__main__":
    main()
