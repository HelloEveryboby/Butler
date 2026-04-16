from butler.core.base_skill import BaseSkill

class DockerManagerSkill(BaseSkill):
    def __init__(self):
        super().__init__("docker_manager")

    def handle_request(self, action, **kwargs):
        if action == "list":
            success, output = self.execute_dynamic_script("shell", "docker ps -a", purpose="List all docker containers")
            return output if success else "执行失败，请检查 Docker 是否安装并运行。"

        elif action == "deploy":
            image = kwargs.get("image") or kwargs.get("entities", {}).get("image")
            if not image:
                return "请指定要部署的 Docker 镜像。"

            def do_deploy(data):
                script = f"docker pull {image} && docker run -d {image}"
                self.execute_dynamic_script("shell", script, purpose=f"Deploying docker image: {image}")

            self.request_permission(
                title="Docker 部署授权",
                content=f"Docker Manager 请求授权部署镜像: {image}",
                on_authorized=do_deploy
            )
            return f"已发起镜像 {image} 的部署授权请求。"

        return f"DockerManager 不支持动作: {action}"

skill_instance = DockerManagerSkill()

def handle_request(action, **kwargs):
    return skill_instance.handle_request(action, **kwargs)
