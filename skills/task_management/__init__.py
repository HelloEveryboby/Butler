import os
import datetime

TASKS_FILE = "TASKS.md"
TASKS_TEMPLATE = """# Tasks

## Active

## Waiting On

## Someday

## Done
"""


def ensure_tasks_file():
    if not os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            f.write(TASKS_TEMPLATE)
        return True
    return False


def read_tasks():
    ensure_tasks_file()
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return f.read()


def write_tasks(content):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def handle_request(action, **kwargs):
    """
    Handles task management based on the operation and task details.
    Operations: add, view, complete, waiting
    """
    jarvis_app = kwargs.get("jarvis_app")
    entities = kwargs.get("entities", {})

    operation = action or entities.get("operation", "view")
    task_details = entities.get("task_details", "")

    if operation == "view":
        content = read_tasks()
        if jarvis_app:
            jarvis_app.ui_print(content, tag="system_message")
        return f"这是您当前的任务列表：\n{content}"

    elif operation == "add":
        if not task_details:
            return "请提供要添加的任务详情。"

        content = read_tasks()
        # Find ## Active and insert below
        lines = content.splitlines()
        new_lines = []
        inserted = False

        for line in lines:
            new_lines.append(line)
            if line.strip() == "## Active" and not inserted:
                new_lines.append(f"- [ ] **{task_details}**")
                inserted = True

        if not inserted:  # Fallback if header not found
            new_lines.append("## Active")
            new_lines.append(f"- [ ] **{task_details}**")

        write_tasks("\n".join(new_lines))
        return f"已添加任务: {task_details}"

    elif operation == "complete":
        if not task_details:
            return "请提供要完成的任务名称。"

        content = read_tasks()
        lines = content.splitlines()
        new_lines = []
        task_line = ""

        # Simple search for the task
        for i, line in enumerate(lines):
            if task_details in line and "[ ]" in line:
                # Found the task, mark as done
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                # Replace [ ] with [x] and wrap the content in strikethrough
                content_part = line.replace("- [ ]", "").strip()
                task_line = f"- [x] ~~{content_part}~~ ({date_str})"
                # Don't add to new_lines here, we'll move it to Done
                continue
            new_lines.append(line)

        if task_line:
            # Add to Done section
            done_index = -1
            for i, line in enumerate(new_lines):
                if line.strip() == "## Done":
                    done_index = i
                    break

            if done_index != -1:
                new_lines.insert(done_index + 1, task_line)
            else:
                new_lines.append("## Done")
                new_lines.append(task_line)

            write_tasks("\n".join(new_lines))
            return f"任务已完成: {task_details}"
        else:
            return f"未找到未完成的任务: {task_details}"

    elif operation == "waiting":
        if not task_details:
            return "请提供您正在等待的事项。"

        content = read_tasks()
        lines = content.splitlines()
        new_lines = []
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        inserted = False

        for line in lines:
            new_lines.append(line)
            if line.strip() == "## Waiting On" and not inserted:
                new_lines.append(f"- [ ] **{task_details}** - since {date_str}")
                inserted = True

        if not inserted:
            new_lines.append("## Waiting On")
            new_lines.append(f"- [ ] **{task_details}** - since {date_str}")

        write_tasks("\n".join(new_lines))
        return f"已将等待事项加入列表: {task_details}"

    else:
        return f"未知的任务管理操作: {operation}"
