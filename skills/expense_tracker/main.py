"""Butler Expense Tracker Skill - Personal finance tracking with local JSON storage."""
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SKILL_DIR, "expenses.json")

_CATEGORIES = [
    "餐饮", "交通", "购物", "娱乐", "住房", "水电", "医疗",
    "教育", "通讯", "服饰", "日用", "工资", "奖金", "投资", "其他",
]


def _load_data() -> Dict[str, List[Dict]]:
    """加载记账数据。"""
    if not os.path.exists(DATA_FILE):
        return {"records": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "records" not in data:
            data["records"] = []
        return data
    except (json.JSONDecodeError, IOError):
        return {"records": []}


def _save_data(data: Dict) -> None:
    """保存记账数据。"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def add_expense(amount: float, category: str, description: str = "",
                date: str = "", income: bool = False) -> Dict:
    """添加一笔收支记录。"""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"error": f"金额 '{amount}' 无效。"}

    if amount <= 0:
        return {"error": "金额必须大于 0。"}

    if category not in _CATEGORIES:
        category = "其他"

    if not date:
        date = _today_str()

    record = {
        "id": uuid.uuid4().hex[:8],
        "amount": amount,
        "category": category,
        "description": description,
        "date": date,
        "type": "income" if income else "expense",
        "created_at": int(time.time()),
    }

    data = _load_data()
    data["records"].append(record)
    _save_data(data)

    type_str = "收入" if income else "支出"
    return {
        "status": "ok",
        "message": f"已记录{type_str}：{amount:.2f} 元（{category}）",
        "record": record,
    }


def list_expenses(month: str = "", category: str = "",
                  limit: int = 20) -> str:
    """查询记录。"""
    data = _load_data()
    records = data["records"]

    if month:
        records = [r for r in records if r["date"].startswith(month)]
    if category:
        records = [r for r in records if r["category"] == category]

    # 按日期倒序
    records.sort(key=lambda r: r["date"], reverse=True)
    records = records[:limit]

    if not records:
        return "暂无符合条件的记录。"

    lines = [f"### 📋 记账记录 (共 {len(records)} 条)\n"]
    for r in records:
        sign = "+" if r["type"] == "income" else "-"
        color = "💚" if r["type"] == "income" else "💸"
        desc = f" - {r['description']}" if r["description"] else ""
        lines.append(
            f"`{r['id']}` | {r['date']} | {r['category']} | "
            f"{color} {sign}{r['amount']:.2f}{desc}"
        )
    return "\n".join(lines)


def delete_expense(record_id: str) -> Dict:
    """按 ID 删除记录。"""
    data = _load_data()
    before = len(data["records"])
    data["records"] = [r for r in data["records"] if r["id"] != record_id]
    after = len(data["records"])

    if before == after:
        return {"error": f"未找到 ID 为 '{record_id}' 的记录。"}

    _save_data(data)
    return {"status": "ok", "message": f"已删除记录 {record_id}。"}


def generate_report(month: str = "") -> str:
    """生成消费统计报告。"""
    data = _load_data()
    records = data["records"]

    if month:
        records = [r for r in records if r["date"].startswith(month)]
        title = f"{month} 消费报告"
    else:
        title = "全部消费报告"

    if not records:
        return f"### 📊 {title}\n\n暂无记录。"

    total_income = sum(r["amount"] for r in records if r["type"] == "income")
    total_expense = sum(r["amount"] for r in records if r["type"] == "expense")
    balance = total_income - total_expense

    # 按类别统计支出
    cat_expense: Dict[str, float] = {}
    for r in records:
        if r["type"] == "expense":
            cat_expense[r["category"]] = cat_expense.get(r["category"], 0) + r["amount"]

    sorted_cats = sorted(cat_expense.items(), key=lambda x: x[1], reverse=True)

    lines = [
        f"### 📊 {title}",
        "",
        f"| 项目 | 金额 (元) |",
        f"|------|----------|",
        f"| 💰 总收入 | {total_income:.2f} |",
        f"| 💸 总支出 | {total_expense:.2f} |",
        f"| 📈 结余 | {balance:.2f} |",
        "",
        f"**支出类别分布**：",
        "",
    ]

    if sorted_cats:
        max_val = sorted_cats[0][1]
        for cat, val in sorted_cats:
            pct = (val / total_expense * 100) if total_expense > 0 else 0
            bar_len = int(val / max_val * 20) if max_val > 0 else 0
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"- {cat:<6} {bar} {val:>8.2f} ({pct:.1f}%)")
    else:
        lines.append("暂无支出记录。")

    return "\n".join(lines)


def summary() -> str:
    """本月概览。"""
    this_month = datetime.now().strftime("%Y-%m")
    return generate_report(this_month)


def handle_request(action: str, **kwargs) -> Any:
    """Butler 技能入口。"""
    if action in ("add", "record", "run"):
        amount = kwargs.get("amount")
        category = kwargs.get("category", "其他")
        description = kwargs.get("description", kwargs.get("desc", ""))
        date = kwargs.get("date", "")
        income = kwargs.get("income", False)
        if amount is None:
            return "错误：请提供 amount 参数。"
        return add_expense(amount, category, description, date, income)

    if action in ("list", "show"):
        month = kwargs.get("month", "")
        category = kwargs.get("category", "")
        limit = int(kwargs.get("limit", 20))
        return list_expenses(month, category, limit)

    if action in ("delete", "remove"):
        rid = kwargs.get("id", "")
        if not rid:
            return "错误：请提供记录 id。"
        return delete_expense(rid)

    if action in ("report", "stats"):
        month = kwargs.get("month", "")
        return generate_report(month)

    if action == "summary":
        return summary()

    if action == "categories":
        return "可用类别：" + "、".join(_CATEGORIES)

    if action == "help" or not action:
        return (
            "### 💰 Butler 记账本\n\n"
            "**添加记录** (action: `add`):\n"
            "- amount: 金额 (必填)\n"
            "- category: 类别 (默认 '其他')\n"
            "- description: 描述 (可选)\n"
            "- date: 日期 YYYY-MM-DD (默认今天)\n"
            "- income: 是否为收入 (默认 false)\n\n"
            "**查询记录** (action: `list`): month, category, limit\n"
            "**删除记录** (action: `delete`): id\n"
            "**消费报告** (action: `report`): month (可选)\n"
            "**本月概览** (action: `summary`)\n"
            "**类别列表** (action: `categories`)"
        )

    return f"未知动作: {action}"
