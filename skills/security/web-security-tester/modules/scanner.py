from butler.core.sec_utils import SecUtils

class ScannerModule:
    def __init__(self, proxy=None):
        self.proxy = proxy
        self.env = SecUtils.get_proxy_env(proxy)

    def run_sqlmap(self, target, extra_args=None):
        if not SecUtils.check_dependency("sqlmap"):
            return "Error: sqlmap is not installed."

        cmd = ["sqlmap", "-u", target, "--batch", "--random-agent"]
        if extra_args:
            cmd.extend(extra_args)

        return SecUtils.run_safe_command(cmd, env=self.env)

    def run_nuclei(self, target):
        if not SecUtils.check_dependency("nuclei"):
            return "Error: nuclei is not installed."

        cmd = ["nuclei", "-u", target, "-severity", "medium,high,critical"]
        return SecUtils.run_safe_command(cmd, env=self.env)
