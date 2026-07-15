import re
import os
import logging

logger = logging.getLogger("SkillInterceptor")

class SkillInterceptor:
    """
    拦截 LLM 生成的 Shell 命令行，并智能重定向至 Butler 高效且安全的本地原生技能（如格式转换、压缩管理），
    以此避免不必要的直接命令行执行，大幅提升执行效率与系统安全性。
    """

    @classmethod
    def intercept_command(cls, command: str, jarvis_app) -> tuple[bool, str]:
        """
        尝试拦截指令。
        返回 (是否拦截, 拦截执行结果信息)。
        如果返回 True，则说明指令已被成功拦截重定向，不执行原始 Shell 指令。
        """
        cmd_strip = command.strip()
        cmd_lower = cmd_strip.lower()

        # ----------------------------------------------------
        # 1. 快速通道 (Fast Path)：文档/格式转换工具拦截
        # ----------------------------------------------------
        if "pandoc" in cmd_lower or "pdf2docx" in cmd_lower or "libreoffice" in cmd_lower or "soffice" in cmd_lower:
            logger.info(f"SkillInterceptor: 检测到文档转换操作，启动智能拦截: {command}")
            # 解析转换参数 (如输入路径、输出路径、转换格式)
            # 例如: pandoc input.md -o output.html
            input_file = None
            output_file = None
            from_fmt = "md"
            to_fmt = "html"

            # 提取输出文件
            out_match = re.search(r'(?:-o|--output)\s+([^\s]+)', cmd_strip)
            if out_match:
                output_file = out_match.group(1).strip("'\"")

            # 提取格式
            from_match = re.search(r'(?:-f|-r|--from|--read)\s+([^\s]+)', cmd_strip)
            if from_match:
                from_fmt = from_match.group(1).strip("'\"")
            to_match = re.search(r'(?:-t|-w|--to|--write)\s+([^\s]+)', cmd_strip)
            if to_match:
                to_fmt = to_match.group(1).strip("'\"")

            # 提取输入文件
            parts = cmd_strip.split()
            skip_next = False
            for i, p in enumerate(parts):
                if skip_next:
                    skip_next = False
                    continue
                if p.startswith("-"):
                    if p in ["-o", "--output", "-f", "-r", "--from", "--read", "-t", "-w", "--to", "--write"]:
                        skip_next = True
                    continue
                if i == 0:  # 忽略命令本身 (e.g. pandoc)
                    continue
                val = p.strip("'\"")
                if val != output_file:
                    input_file = val

            if input_file and output_file:
                # 若未显式指定格式，从文件后缀推导
                if not from_match:
                    from_fmt = os.path.splitext(input_file)[1].lstrip(".").lower()
                if not to_match:
                    to_fmt = os.path.splitext(output_file)[1].lstrip(".").lower()

                if "format_convert" in jarvis_app.skill_manager.manifests:
                    logger.info(f"SkillInterceptor: 智能重定向至 'format_convert' 原生技能 (源格式={from_fmt}, 目标格式={to_fmt}, 输入文件={input_file}, 输出目标={output_file})")

                    try:
                        res = jarvis_app.skill_manager.execute(
                            "format_convert",
                            "run",
                            input=input_file,
                            from_fmt=from_fmt,
                            to_fmt=to_fmt,
                            save_to=output_file,
                            jarvis_app=jarvis_app
                        )
                        return True, f"✨ [智能拦截成功] 检测到底层转换命令，已为您静默重定向并调用 Butler 专属原生格式转换服务（format_convert）：\n{res}"
                    except Exception as e:
                        logger.error(f"SkillInterceptor: format_convert 本地技能调用失败: {e}")

        # ----------------------------------------------------
        # 2. 快速通道 (Fast Path)：压缩/打包工具拦截
        # ----------------------------------------------------
        if "zip" in cmd_lower or "unzip" in cmd_lower or "tar" in cmd_lower:
            logger.info(f"SkillInterceptor: 检测到压缩解压操作，启动智能拦截: {command}")
            if "archive_manager" in jarvis_app.skill_manager.manifests:
                zip_path = None
                target_paths = []
                action = "zip" if "zip" in cmd_lower and "unzip" not in cmd_lower else "unzip"

                if action == "zip":
                    # e.g., zip -r archive.zip folder1 file2
                    parts = cmd_strip.split()
                    for p in parts[2:]:
                        p_clean = p.strip("'\"")
                        if not p_clean.startswith("-"):
                            if not zip_path:
                                zip_path = p_clean
                            else:
                                target_paths.append(p_clean)
                else:
                    # e.g., unzip archive.zip -d dest_dir
                    parts = cmd_strip.split()
                    for p in parts[1:]:
                        p_clean = p.strip("'\"")
                        if not p_clean.startswith("-") and p_clean != "-d":
                            zip_path = p_clean
                            break

                if zip_path:
                    try:
                        logger.info(f"SkillInterceptor: 智能重定向至 'archive_manager' 原生技能 (操作={action}, 压缩包路径={zip_path})")
                        res = jarvis_app.skill_manager.execute(
                            "archive_manager",
                            "run",
                            action=action,
                            zip_path=zip_path,
                            targets=target_paths,
                            jarvis_app=jarvis_app
                        )
                        return True, f"✨ [智能拦截成功] 检测到压缩/解包命令，已为您静默重定向并调用 Butler 专属高效本地文件压缩管理服务（archive_manager）：\n{res}"
                    except Exception as e:
                        logger.error(f"SkillInterceptor: archive_manager 本地技能调用失败: {e}")

        # ----------------------------------------------------
        # 3. 慢速通道 (Slow Path)：基于关键字/描述的隐式技能重定向
        # ----------------------------------------------------
        if hasattr(jarvis_app, 'skill_manager') and hasattr(jarvis_app.skill_manager, 'manifests'):
            for skill_id, manifest in jarvis_app.skill_manager.manifests.items():
                keywords = [k.lower() for k in manifest.get("keywords", [])]
                for kw in keywords:
                    if kw and kw in cmd_lower:
                        logger.info(f"SkillInterceptor: 指令关键字 '{kw}' 命中本地技能 '{skill_id}'。自动重定向。")
                        try:
                            res = jarvis_app.skill_manager.execute(
                                skill_id,
                                "run",
                                command=cmd_strip,
                                jarvis_app=jarvis_app
                            )
                            return True, f"✨ [智能拦截成功] 发现与本地原生技能高度契合的操作 (技能: {skill_id})，已自动切换至安全且高效的内部服务，避开了直接命令行执行:\n{res}"
                        except Exception as e:
                            logger.error(f"SkillInterceptor: 本地技能 {skill_id} 自动重定向执行失败: {e}")

        return False, ""
