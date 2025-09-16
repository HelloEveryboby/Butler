import time
import logging
from .abstract_plugin import AbstractPlugin

class CountdownPlugin(AbstractPlugin):
    def get_name(self) -> str:
        return "CountdownPlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("CountdownPlugin initialized.")

    def get_commands(self) -> list[str]:
        return ["countdown", "倒计时"]

    def run(self, command: str, args: dict) -> str:
        """
        Runs a countdown for a specified number of seconds.
        NOTE: This is a blocking operation and will freeze the main thread.
        A future improvement would be to run this in a background thread.
        """
        try:
            seconds = int(args.get("seconds", 0))
        except (ValueError, TypeError):
            return "Error: Please provide a valid number of seconds."

        if seconds <= 0:
            return "Error: Please provide a positive number of seconds for the countdown."

        self.logger.info(f"Starting a blocking countdown for {seconds} seconds.")
        time.sleep(seconds)
        self.logger.info("Countdown finished.")

        return f"Countdown of {seconds} seconds is complete."

    def stop(self):
        # In a non-blocking implementation, this would stop the countdown thread.
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        # A non-blocking version could return the remaining time.
        return "active"
