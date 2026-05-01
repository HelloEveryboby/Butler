import json
p = json.load(open("butler/prompts.json", encoding="utf-8"))
prompt = p["nlu_intent_extraction"]["prompt"]
new_intent = "- `take_screenshot`: 执行高级截图。需要 `type` ('full', 'region', 'web', 'window')，若是 'web' 类型则需要 `url` 实体。"
if new_intent not in prompt:
    p["nlu_intent_extraction"]["prompt"] = prompt.replace("- `exit`: 退出程序。", new_intent + "\n- `exit`: 退出程序。")
with open("butler/prompts.json", "w", encoding="utf-8") as f:
    json.dump(p, f, indent=2, ensure_ascii=False)
