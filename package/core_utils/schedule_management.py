import json
import os
import pyttsx3
import datetime
import schedule
import time
import threading

class ScheduleManager:
    def __init__(self, jarvis, filename='schedule.json'):
        self.jarvis = jarvis
        self.filename = filename
        self.load_schedule()

    def speak(self, message):
        self.jarvis.speak(message)

    def takecommand(self):
        return self.jarvis.takecommand()

    def load_schedule(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as file:
                self.schedule = json.load(file)
        else:
            self.schedule = []

    def save_schedule(self):
        with open(self.filename, 'w') as file:
            json.dump(self.schedule, file, indent=4)

    def add_event(self, date_time, event, reminder=None, repeat=None):
        try:
            datetime_obj = datetime.datetime.strptime(date_time, "%Y-%m-%d %H:%M")
            self.schedule.append({'date': datetime_obj.strftime("%Y-%m-%d %H:%M"),
                                  'event': event,
                                  'reminder': reminder,
                                  'repeat': repeat})
            self.save_schedule()
            self.speak(f'事件 "{event}" 已添加到 {date_time}')
            # 添加重复事件到 schedule 库
            if repeat:
                self.schedule_event(datetime_obj, event, repeat)
        except ValueError:
            self.speak("日期或时间格式错误，请重新输入。")

    def schedule_event(self, datetime_obj, event, repeat):
        if repeat == '每天':
            schedule.every().day.at(datetime_obj.strftime("%H:%M")).do(self.event_reminder, event)
        elif repeat == '每周':
            schedule.every().week.at(datetime_obj.strftime("%H:%M")).do(self.event_reminder, event)
        elif repeat == '每月':
            schedule.every().month.at(datetime_obj.strftime("%H:%M")).do(self.event_reminder, event)

    def event_reminder(self, event):
        self.speak(f"提醒：{event}")

    def run_scheduler(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

    def view_schedule(self):
        if not self.schedule:
            self.speak('没有已安排的事件。')
        else:
            # 按时间排序
            self.schedule.sort(key=lambda item: datetime.datetime.strptime(item['date'], "%Y-%m-%d %H:%M"))
            for idx, entry in enumerate(self.schedule, start=1):
                self.speak(f"{idx}. {entry['date']} - {entry['event']}")

    def search_event(self, keyword):
        found = False
        for entry in self.schedule:
            if keyword.lower() in entry['event'].lower():
                self.speak(f"{entry['date']} - {entry['event']}")
                found = True
        if not found:
            self.speak("没有找到匹配的事件。")

    def delete_event(self, index):
        try:
            removed = self.schedule.pop(index - 1)
            self.save_schedule()
            self.speak(f'事件 "{removed["event"]}" 在 {removed["date"]} 已删除。')
        except IndexError:
            self.speak('无效的事件编号。')

    def edit_event(self, index, new_date_time=None, new_event=None):
        try:
            event = self.schedule[index - 1]
            if new_date_time:
                datetime_obj = datetime.datetime.strptime(new_date_time, "%Y-%m-%d %H:%M")
                event['date'] = datetime_obj.strftime("%Y-%m-%d %H:%M")
            if new_event:
                event['event'] = new_event
            self.save_schedule()
            self.speak(f'事件已更新：{event["date"]} - {event["event"]}')
            # 如果存在重复事件，则需要更新重复事件调度
            if 'repeat' in event and event['repeat']:
                self.schedule_event(datetime_obj, event['event'], event['repeat'])
        except IndexError:
            self.speak('无效的事件编号。')
        except ValueError:
            self.speak("日期或时间格式错误，请重新输入。")

    def add_relative_event(self, time_delta, event):
        now = datetime.datetime.now()
        future_time = now + datetime.timedelta(minutes=time_delta)
        self.add_event(future_time.strftime("%Y-%m-%d %H:%M"), event)

    def add_event_relative(self, time_str, event):
        try:
            if '分钟' in time_str:
                time_delta = int(time_str.split('分钟')[0].strip())
                self.add_relative_event(time_delta, event)
            elif '小时' in time_str:
                hours = int(time_str.split('小时')[0].strip())
                time_delta = hours * 60
                self.add_relative_event(time_delta, event)
            elif '天' in time_str:
                days = int(time_str.split('天')[0].strip())
                future_date = datetime.datetime.now() + datetime.timedelta(days=days)
                self.speak("请输入具体时间，格式为 HH:MM。")
                time = takecommand()
                if time:
                    event_datetime = future_date.strftime("%Y-%m-%d") + " " + time
                    self.add_event(event_datetime, event)
            else:
                self.speak("无效的时间格式，请重新输入。")
        except ValueError:
            self.speak("时间格式错误，请重新输入。")
