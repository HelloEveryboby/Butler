import random
import time

jokes = [
    ("为什么企鹅不会飞？", "因为他们太胖了！"),
    ("为什么树木总是在看地图？", "因为它们总是迷路！"),
    ("为什么蜗牛总是背着房子？", "因为它们太宅了！"),
    ("为什么小明总是喜欢玩游戏？", "因为游戏比学习有趣多了！"),
    ("为什么老师总是喜欢提问？", "因为他们想看看学生有没有认真听课！"),
    ("为什么猪总是喜欢睡觉？", "因为他们太懒了！"),
]

def handle_request(action, **kwargs):
    jarvis = kwargs.get("jarvis_app")
    joke_question, joke_answer = random.choice(jokes)

    if jarvis:
        jarvis.speak(joke_question)
        time.sleep(3)
        jarvis.speak(joke_answer)
        return f"{joke_question} {joke_answer}"

    return f"问题：{joke_question}\n答案：{joke_answer}"
