# -*- coding: utf-8 -*-
def run(input_data=None, **kwargs):
    print("【邮件技能】正在抓取收件箱...")
    return {
        "status": "success",
        "emails": [
            {"id": "1", "from": "partner@co.com", "subject": "紧急报价方案确认", "body": "请立即查看最新报价，明天下午需要签署合同。"},
            {"id": "2", "from": "admin@butler.io", "subject": "系统周报摘要", "body": "服务正常运行率 99.9%，CPU 负载在健康水平。"}
        ]
    }
