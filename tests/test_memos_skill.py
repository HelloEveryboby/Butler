import os
import sys

# 添加项目根目录到 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from skills.memos import handle_request

def test_memos():
    print("--- Testing Memos Skill ---")

    # 1. Add a memo
    print("\nAdding a memo...")
    res_add = handle_request("add", content="Hello Butler! This is a **markdown** memo. #test", tags=["#test"])
    print(res_add)

    # 2. List memos
    print("\nListing memos...")
    res_list = handle_request("list", limit=5)
    print(res_list)

    # 3. Search memos
    print("\nSearching for 'markdown'...")
    res_search = handle_request("search", query="markdown")
    print(res_search)

    # 4. Delete memo
    if isinstance(res_list, list) and len(res_list) > 0:
        memo_id = res_list[0]['id']
        print(f"\nDeleting memo ID: {memo_id}...")
        res_del = handle_request("delete", id=memo_id)
        print(res_del)

if __name__ == "__main__":
    test_memos()
