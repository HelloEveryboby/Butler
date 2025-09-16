import random
import logging
from .abstract_plugin import AbstractPlugin

class JokePlugin(AbstractPlugin):
    def __init__(self):
        self.jokes = [
            ("为什么企鹅不会飞？", "因为他们太胖了！"),
            ("为什么树木总是在看地图？", "因为它们总是迷路！"),
            ("为什么蜗牛总是背着房子？", "因为它们太宅了！"),
            ("为什么小明总是喜欢玩游戏？", "因为游戏比学习有趣多了！"),
            ("为什么老师总是喜欢提问？", "因为他们想看看学生有没有认真听课！"),
            ("为什么猪总是喜欢睡觉？", "因为他们太懒了！"),
        ]

    def get_name(self) -> str:
        return "JokePlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("JokePlugin initialized.")

    def get_commands(self) -> list[str]:
        return ["讲个笑话", "来个笑话", "我无聊了"]

    def run(self, command: str, args: dict) -> str:
        joke_question, joke_answer = random.choice(self.jokes)
        return f"{joke_question}\n...\n{joke_answer}"

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "active"
