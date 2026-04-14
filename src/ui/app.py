import streamlit as st

st.set_page_config(
    page_title="Орикс ИИ-аналитика",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Орикс — Аналитические выводы")
st.success("✅ Sprint 1 завершён — инфраструктура готова!")
st.divider()

st.subheader("📊 Архитектура системы (3 уровня):")
st.markdown("""
- **Шаг 1:** Детерминированные расчёты → `deterministic/`
- **Шаг 2:** Генерация текста (LLM) → `nlg/`
- **Шаг 3:** Авто-валидация → `validation/`
""")
st.divider()

st.subheader("📋 Статус метрик:")
st.markdown("""
| Метрика | Статус |
|---------|--------|
| 1. Доля потерь | ⏳ Sprint 2 |
| 2. Прямые потери | ⏳ Sprint 3 |
| 3. Чистые потери | ⏳ Sprint 4 |
| 4. Уровень возмещения | ⏳ Sprint 4 |
| 5. Концентрация | ⏳ Sprint 5 |
| 6. КПУР | ⏳ Sprint 5 |
""")
st.divider()

st.info("🎯 Цель: генерация выводов с качеством < 5% ошибок")