# tests/unit/test_llm.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.nlg.llm_service import LLMService

def test_llm_connection():
    llm = LLMService()
    result = llm.generate("Скажи 'API работает' и ничего больше.")
    print(f"Ответ LLM: {result}")
    assert len(result) > 0
    print("LLM подключён успешно")

if __name__ == "__main__":
    test_llm_connection()