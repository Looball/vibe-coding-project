"""问候语识别测试。"""
from app.rag.greeting import detect_greeting


def test_common_greetings_recognized():
    for g in ["你好", "您好", "早上好", "嗨", "Hello", "hi", "老师好"]:
        assert detect_greeting(g) is not None, g


def test_thanks_and_farewell_recognized():
    assert "不客气" in detect_greeting("谢谢")
    assert detect_greeting("感谢你的解答") is not None
    assert "再见" in detect_greeting("拜拜")


def test_question_is_not_greeting():
    assert detect_greeting("什么是大语言模型？") is None
    assert detect_greeting("如何安装 java？") is None
