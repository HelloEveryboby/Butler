from butler.core.sec_utils import SecUtils

class ReconModule:
    def __init__(self, proxy=None):
        self.proxy = proxy
        self.env = SecUtils.get_proxy_env(proxy)

    def run_nmap(self, target):
        if not SecUtils.check_dependency("nmap"):
            return "Error: nmap is not installed."

        cmd = ["nmap", "-sV", "-T4", target]
        return SecUtils.run_safe_command(cmd, env=self.env)

    def run_discovery(self, target):
        # Prefer ffuf, fallback to dirsearch
        tool = "ffuf" if SecUtils.check_dependency("ffuf") else "dirsearch"
        if not SecUtils.check_dependency(tool):
            return f"Error: Neither ffuf nor dirsearch is installed."

        if tool == "ffuf":
            # Use a more generic wordlist approach or allow user to specify
            wordlist = os.environ.get("SEC_WORDLIST", "/usr/share/wordlists/dirb/common.txt")
            if not os.path.exists(wordlist):
                 return f"Error: Wordlist not found at {wordlist}. Please set SEC_WORDLIST env var."
            cmd = ["ffuf", "-u", f"{target}/FUZZ", "-w", wordlist]
        else:
            cmd = ["dirsearch", "-u", target, "-e", "php,html,js,json"]

        return SecUtils.run_safe_command(cmd, env=self.env)
