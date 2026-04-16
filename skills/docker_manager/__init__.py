import logging
from butler.core.base_skill import BaseSkill

class DockerManagerSkill(BaseSkill):
    """
    Docker 配置器技能类。
    定位：自动化运维助手。
    功能：根据实际需求自动执行容器化的各种复杂操作。
    """
    def __init__(self):
        super().__init__("docker_manager")
        self.logger = logging.getLogger("DockerManager")

    def handle_request(self, action, **kwargs):
        """
        统一请求处理入口。
        支持的操作:
          - list: 列出所有容器。
          - deploy: 自动化部署镜像。
        """
        if action == "list":
            success, output = self.execute_dynamic_script(
                "shell",
                "docker ps -a --format \"table {{.Names}}\t{{.Status}}\t{{.Image}}\"",
                purpose="获取当前系统所有 Docker 容器列表"
            )
            if not success:
                return "❌ 执行失败，请检查 Docker 服务是否已启动并具有相应权限。"
            return f"### 当前容器列表：\n{output}"

        elif action == "deploy":
            image = kwargs.get("image") or kwargs.get("entities", {}).get("image")
            if not image:
                return "❌ 请指定要部署的 Docker 镜像名称。"

            # 定义授权后的部署逻辑
            def do_deploy(data):
                self.logger.info(f"授权通过，开始部署镜像: {image}")
                script = f"docker pull {image} && docker run -d --name butler_{image.replace(':', '_')} {image}"
                self.execute_dynamic_script(
                    "shell",
                    script,
                    purpose=f"自动化部署容器化服务: {image}"
                )

            # 发起部署授权请求
            self.request_permission(
                title="📦 Docker 自动化部署请求",
                content=f"Docker Manager 请求授权下载并运行镜像: {image}。此操作将消耗系统资源并开启新的网络端口。",
                on_authorized=do_deploy
            )
            return f"⏳ 已发起镜像 {image} 的部署申请。请在通知栏进行审批。"

        return f"错误: DockerManager 不支持动作 '{action}'。"

# 实例化技能
skill_instance = DockerManagerSkill()

def handle_request(action, **kwargs):
    """
    对接 Butler SkillManager 的标准入口函数。
    """
    return skill_instance.handle_request(action, **kwargs)
