"""Butler Habit Tracker Skill - Habit check-in and streak tracking."""
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SKILL_DIR, "habits.json")


def _load_data() -> Dict:
    if not os.path.exists(DATA_FILE):
        return {"habits": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "habits" not in data:
            data["habits"] = {}
        return data
    except (json.JSONDecodeError, IOError):
        return {"habits": {}}


def _save_data(data: Dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _calc_streak(checkins: List[str]) -> int:
    """计算当前连续打卡天数（从今天或昨天开始回溯）。"""
    if not checkins:
        return 0
    checkin_set = set(checkins)
    streak = 0
    day = datetime.now().date()

    # 如果今天没打卡，从昨天开始算
    if _today() not in checkin_set:
        day -= timedelta(days=1)

    while day.strftime("%Y-%m-%d") in checkin_set:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _calc_longest_streak(checkins: List[str]) -> int:
    """计算历史最长连续天数。"""
    if not checkins:
        return 0
    sorted_dates = sorted(checkins)
    longest = 1
    current = 1
    for i in range(1, len(sorted_dates)):
        d1 = datetime.strptime(sorted_dates[i - 1], "%Y-%m-%d").date()
        d2 = datetime.strptime(sorted_dates[i], "%Y-%m-%d").date()
        if (d2 - d1).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def create_habit(name: str, description: str = "", weekly_goal: int = 7) -> Dict:
    """创建新习惯。"""
    if not name or not name.strip():
        return {"error": "习惯名称不能为空。"}
    name = name.strip()

    data = _load_data()
    if name in data["habits"]:
        return {"error": f"习惯 '{name}' 已存在。"}

    data["habits"][name] = {
        "description": description,
        "weekly_goal": min(max(int(weekly_goal), 1), 7),
        "checkins": [],
        "created_at": _today(),
    }
    _save_data(data)
    return {"status": "ok", "message": f"已创建习惯：{name}"}


def checkin(name: str, date: str = "") -> Dict:
    """打卡。"""
    data = _load_data()
    if name not in data["habits"]:
        return {"error": f"习惯 '{name}' 不存在。"}

    date = date or _today()
    checkins = data["habits"][name]["checkins"]
    if date in checkins:
        return {"status": "skip", "message": f"{date} 已打卡过了。"}

    checkins.append(date)
    _save_data(data)
    streak = _calc_streak(checkins)
    return {
        "status": "ok",
        "message": f"✅ {name} 打卡成功！连续 {streak} 天。",
        "streak": streak,
    }


def uncheck(name: str, date: str = "") -> Dict:
    """取消打卡。"""
    data = _load_data()
    if name not in data["habits"]:
        return {"error": f"习惯 '{name}' 不存在。"}

    date = date or _today()
    checkins = data["habits"][name]["checkins"]
    if date not in checkins:
        return {"status": "skip", "message": f"{date} 没有打卡记录。"}

    checkins.remove(date)
    _save_data(data)
    return {"status": "ok", "message": f"已取消 {name} 在 {date} 的打卡。"}


def delete_habit(name: str) -> Dict:
    """删除习惯。"""
    data = _load_data()
    if name not in data["habits"]:
        return {"error": f"习惯 '{name}' 不存在。"}
    del data["habits"][name]
    _save_data(data)
    return {"status": "ok", "message": f"已删除习惯：{name}"}


def status() -> str:
    """查看所有习惯进度。"""
    data = _load_data()
    habits = data["habits"]
    if not habits:
        return "### 🎯 习惯追踪\n\n暂无习惯，使用 `create` 创建第一个吧！"

    today = _today()
    lines = ["### 🎯 习惯进度\n"]

    for name, info in habits.items():
        checkins = info["checkins"]
        streak = _calc_streak(checkins)
        longest = _calc_longest_streak(checkins)

        # 本周完成率
        now = datetime.now()
        week_start = (now - timedelta(days=now.weekday())).date()
        week_checkins = [
            c for c in checkins
            if datetime.strptime(c, "%Y-%m-%d").date() >= week_start
        ]
        weekly_rate = len(week_checkins) / info["weekly_goal"] * 100
        rate_bar = int(weekly_rate / 10)
        rate_str = "█" * rate_bar + "░" * (10 - rate_bar)

        # 近 14 天打卡日历
        calendar = []
        for i in range(13, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            calendar.append("✓" if d in checkins else "·")
        cal_str = " ".join(calendar)

        done_today = today in checkins
        icon = "✅" if done_today else "⬜"

        lines.append(f"{icon} **{name}**")
        lines.append(f"   🔥 当前连续: {streak} 天 | 🏆 最长: {longest} 天")
        lines.append(f"   本周: [{rate_str}] {weekly_rate:.0f}%")
        lines.append(f"   近14天: {cal_str}")
        lines.append("")

    return "\n".join(lines)


def today_overview() -> str:
    """今日概览。"""
    data = _load_data()
    habits = data["habits"]
    if not habits:
        return "暂无习惯。"

    today = _today()
    done = []
    pending = []
    for name in habits:
        if today in habits[name]["checkins"]:
            done.append(name)
        else:
            pending.append(name)

    lines = [f"### 📅 今日概览 ({today})\n"]
    lines.append(f"**已完成 ({len(done)})**:")
    for n in done:
        lines.append(f"  ✅ {n}")
    lines.append(f"\n**待完成 ({len(pending)})**:")
    for n in pending:
        lines.append(f"  ⬜ {n}")
    return "\n".join(lines)


def handle_request(action: str, **kwargs) -> Any:
    """Butler 技能入口。"""
    if action in ("create", "add", "new"):
        name = kwargs.get("name", "")
        desc = kwargs.get("description", kwargs.get("desc", ""))
        goal = int(kwargs.get("weekly_goal", 7))
        return create_habit(name, desc, goal)

    if action in ("checkin", "check", "done", "run"):
        name = kwargs.get("name", kwargs.get("habit", ""))
        date = kwargs.get("date", "")
        if not name:
            return "错误：请提供 name 参数。"
        return checkin(name, date)

    if action in ("uncheck", "undo"):
        name = kwargs.get("name", kwargs.get("habit", ""))
        date = kwargs.get("date", "")
        if not name:
            return "错误：请提供 name 参数。"
        return uncheck(name, date)

    if action in ("delete", "remove"):
        name = kwargs.get("name", kwargs.get("habit", ""))
        if not name:
            return "错误：请提供 name 参数。"
        return delete_habit(name)

    if action in ("status", "list", "show"):
        return status()

    if action in ("today", "overview"):
        return today_overview()

    if action == "help" or not action:
        return (
            "### 🎯 Butler 习惯追踪器\n\n"
            "**创建习惯** (action: `create`): name, description, weekly_goal\n"
            "**打卡** (action: `checkin`): name, date (可选)\n"
            "**取消打卡** (action: `uncheck`): name, date (可选)\n"
            "**查看进度** (action: `status`)\n"
            "**今日概览** (action: `today`)\n"
            "**删除习惯** (action: `delete`): name"
        )

    return f"未知动作: {action}"
