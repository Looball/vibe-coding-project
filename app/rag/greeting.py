"""日常问候语识别（PRD 2.2.3）。

轻量启发式匹配常见中文问候/致谢语；命中则返回友好回复，未命中返回 None
（走 RAG 检索问答）。需更精确可用 LLM 分类，但问候语集合固定，启发式足够。
"""
from __future__ import annotations

_GREETINGS = [
    "你好", "您好", "嗨", "hello", "hi", "早上好", "下午好", "晚上好",
    "大家好", "哈喽", "老师好",
]
_THANKS = ["谢谢", "感谢", "多谢", "辛苦了", "thank", "thanks"]
_FAREWELL = ["再见", "拜拜", "回头见", "bye"]


def detect_greeting(text: str) -> str | None:
    """若输入为问候/致谢/道别，返回友好回复；否则返回 None。"""
    t = text.strip().lower()
    if not t:
        return None

    for w in _GREETINGS:
        if w.lower() in t:
            return "你好呀！我是智能助教，欢迎提出学习问题～请问想了解哪方面的知识？"

    for w in _THANKS:
        if w.lower() in t:
            return "不客气，能帮到你就好。还有别的问题随时问我～"

    for w in _FAREWELL:
        if w.lower() in t:
            return "再见！祝你学习顺利，有需要随时来找我～"

    return None
