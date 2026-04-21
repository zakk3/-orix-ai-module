# src/ui/app.py

import os, sys, json, base64
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.input_models import GenerationRequest, OrixMetricInput, OrixSeriesItem
from src.models.enums import MetricType
from src.core.pipeline import AnalysisPipeline
from src.core.validation.input_validator import InputValidator

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "orix_logo.png")

METRICS = [
    ("1. Доля потерь в бизнес-индикаторе",     MetricType.LOSS_SHARE.value),
    ("2. Динамика прямых потерь",               MetricType.DIRECT_LOSSES_DYNAMICS.value),
    ("3. Динамика чистых потерь",               MetricType.NET_LOSSES_DYNAMICS.value),
    ("4. Уровень возмещения",                   MetricType.RECOVERY_LEVEL.value),
    ("5. Области концентрации",                 MetricType.CONCENTRATION.value),
    ("6. Нарушение КПУР",                       MetricType.KPUR_VIOLATION.value),
]

st.set_page_config(page_title="Orix AI Module", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Onest:wght@400;500;600;700&display=swap');
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif !important; background: #ffffff !important; color: #0d1b2a !important; }
[data-testid="collapsedControl"], [data-testid="stSidebar"], section[data-testid="stSidebar"],
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
.orix-nav, .orix-hero, .orix-form-wrap, .orix-result-wrap { padding-left: 64px !important; padding-right: 64px !important; }
.orix-hr { margin: 0 64px !important; }
.orix-nav { display: flex; align-items: center; padding-top: 16px; padding-bottom: 16px; border-bottom: 1px solid #e8edf2; background: #ffffff; }
.orix-nav-logo { display: flex; align-items: center; gap: 14px; }
.orix-nav-logo img { height: 40px; width: auto; }
.orix-nav-brand { font-family: 'Onest', sans-serif; font-size: 22px; font-weight: 700; color: #0d1b2a; letter-spacing: 0.5px; }
.orix-hero { padding-top: 48px; padding-bottom: 36px; max-width: 900px; }
.orix-hero-title { font-size: 42px; font-weight: 800; color: #0d1b2a; line-height: 1.15; letter-spacing: -1px; margin-bottom: 18px; }
.orix-hero-desc { font-size: 16px; font-weight: 400; color: #4a6070; line-height: 1.7; }
.orix-hr { border: none; border-top: 1px solid #e8edf2; }
.orix-form-wrap { padding-top: 32px; padding-bottom: 8px; }
div[data-testid="stSelectbox"] label, div[data-testid="stTextArea"] label,
div[data-testid="stFileUploader"] label, div[data-testid="stTextInput"] label {
    font-family: 'Inter', sans-serif !important; font-size: 11px !important;
    font-weight: 700 !important; color: #6b8ca8 !important;
    letter-spacing: 0.6px !important; text-transform: uppercase !important; }
div[data-testid="stSelectbox"], div[data-testid="stTextArea"],
div[data-testid="stFileUploader"], div[data-testid="stTextInput"] { margin-bottom: 14px !important; }
div[data-testid="stSelectbox"] > div > div {
    border: 1.5px solid #b8d0e8 !important; border-radius: 8px !important;
    background: #ffffff !important; font-size: 14px !important; font-weight: 500 !important;
    color: #0d1b2a !important; min-height: 42px !important; box-shadow: none !important; }
div[data-testid="stSelectbox"] > div > div:hover { border-color: #3b7de9 !important; }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background: #ffffff !important; color: #0d1b2a !important; }
div[data-baseweb="popover"], div[data-baseweb="popover"] > div, ul[role="listbox"], div[role="listbox"] {
    background: #ffffff !important; border: 1.5px solid #b8d0e8 !important;
    border-radius: 8px !important; box-shadow: 0 8px 24px rgba(13,27,42,0.1) !important; }
li[role="option"], div[role="option"] { font-size: 14px !important; color: #0d1b2a !important; background: #ffffff !important; padding: 10px 16px !important; }
li[role="option"]:hover, div[role="option"]:hover, li[aria-selected="true"], div[aria-selected="true"] { background: #eff5fd !important; color: #3b7de9 !important; }
div[data-testid="stTextArea"] > div { background: #ffffff !important; border: none !important; }
div[data-testid="stTextArea"] textarea {
    border: 1.5px solid #b8d0e8 !important; border-radius: 8px !important; background: #ffffff !important;
    font-family: 'Courier New', monospace !important; font-size: 13px !important;
    color: #0d1b2a !important; padding: 14px 16px !important; resize: none !important;
    scrollbar-width: thin !important; scrollbar-color: #b8d0e8 transparent !important; }
div[data-testid="stTextArea"] textarea:focus { border-color: #3b7de9 !important; box-shadow: 0 0 0 3px rgba(59,125,233,0.1) !important; outline: none !important; }
div[data-testid="stTextArea"] [data-baseweb="textarea"], div[data-testid="stTextArea"] [data-baseweb="base-input"] { background: #ffffff !important; border: none !important; }
[data-testid="stFileUploader"] section, [data-testid="stFileUploaderDropzone"] {
    border: 1.5px solid #b8d0e8 !important; border-radius: 8px !important;
    background: #ffffff !important; padding: 14px 18px !important; min-height: 60px !important; }
[data-testid="stFileUploader"] button {
    background: #3b7de9 !important; color: #ffffff !important; border: none !important;
    border-radius: 6px !important; font-size: 0 !important; padding: 0 18px !important;
    min-height: 36px !important; min-width: 130px !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important; position: relative !important; }
[data-testid="stFileUploader"] button::after { content: "Загрузить" !important; color: #ffffff !important; font-size: 13px !important; font-weight: 600 !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stFileUploader"] button > * { display: none !important; }
[data-testid="stFileUploader"] button:hover { background: #2a6bd4 !important; }
[data-testid="stFileUploader"] small, [data-testid="stFileUploader"] p,
[data-testid="stFileUploader"] span, [data-testid="stFileUploaderDropzoneInstructions"] * { color: #6b8ca8 !important; font-size: 12px !important; background: transparent !important; }
div[data-testid="stTextInput"] input {
    border: 1.5px solid #b8d0e8 !important; border-radius: 8px !important; background: #ffffff !important;
    font-size: 14px !important; font-weight: 500 !important; color: #0d1b2a !important;
    padding: 10px 14px !important; min-height: 42px !important; }
div[data-testid="stTextInput"] input:focus { border-color: #3b7de9 !important; box-shadow: 0 0 0 3px rgba(59,125,233,0.1) !important; }
div[data-testid="stButton"] > button {
    background: #3b7de9 !important; color: #ffffff !important; border: none !important;
    border-radius: 8px !important; font-size: 14px !important; font-weight: 600 !important;
    padding: 12px 32px !important; margin-top: 12px !important; transition: all 0.15s ease !important; }
div[data-testid="stButton"] > button:hover { background: #2a6bd4 !important; transform: translateY(-1px) !important; box-shadow: 0 4px 14px rgba(59,125,233,0.25) !important; }
.orix-result-wrap { padding-top: 36px; padding-bottom: 56px; }
.orix-section-label { font-size: 11px; font-weight: 700; color: #6b8ca8; letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 16px; }
.orix-metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }
.orix-metric-card { background: #ffffff; border: 1.5px solid #b8d0e8; border-radius: 10px; padding: 16px 18px; }
.orix-metric-card-label { font-size: 10px; font-weight: 700; color: #6b8ca8; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 8px; }
.orix-metric-card-value { font-size: 26px; font-weight: 700; color: #0d1b2a; letter-spacing: -0.5px; line-height: 1; }
.orix-metric-card-value.down { color: #1a7a4a; }
.orix-metric-card-value.up   { color: #c0392b; }
.orix-rank-pill { display: inline-flex; align-items: center; background: #eff5fd; border: 1.5px solid #b8d0e8; border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 600; color: #1a3a5c; margin-bottom: 18px; }
.orix-verdict { background: #ffffff; border: 1.5px solid #b8d0e8; border-left: 4px solid #3b7de9; border-radius: 10px; padding: 22px 26px; margin-bottom: 14px; }
.orix-verdict-header { font-size: 10px; font-weight: 700; color: #3b7de9; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 12px; }
.orix-verdict-body { font-size: 15px; font-weight: 400; color: #0d1b2a; line-height: 1.7; }
.orix-quality { display: flex; align-items: center; gap: 32px; background: #ffffff; border: 1.5px solid #b8d0e8; border-radius: 8px; padding: 12px 20px; font-size: 13px; color: #4a6070; font-weight: 500; }
.orix-quality strong { color: #0d1b2a; font-weight: 700; }
div[data-testid="stAlert"] { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)


def get_logo_html() -> str:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" />'
    # SVG-заглушка если логотип не найден
    return """<svg width="42" height="38" viewBox="0 0 42 38" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="42" height="38" rx="10" fill="url(#og)"/>
      <path d="M13 19C13 14.582 16.582 11 21 11C25.418 11 29 14.582 29 19C29 23.418 25.418 27 21 27" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M21 27C18.5 27 16.5 25 16.5 19" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
      <defs><linearGradient id="og" x1="0" y1="0" x2="42" y2="38">
        <stop offset="0%" stop-color="#5b8ef0"/><stop offset="100%" stop-color="#8b5cf6"/>
      </linearGradient></defs></svg>"""


st.markdown(f"""
<div class="orix-nav">
    <div class="orix-nav-logo">{get_logo_html()}<span class="orix-nav-brand">ОРИКС</span></div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="orix-hero">
    <div class="orix-hero-title">Автоматический анализ<br>операционных рисков</div>
    <div class="orix-hero-desc">
        ИИ-модуль ОРИКС автоматически формирует развёрнутые аналитические выводы по ключевым
        показателям операционного риска банка. Система анализирует шесть направлений: долю потерь
        в бизнес-индикаторе, динамику прямых и чистых потерь, уровень возмещения, области концентрации
        потерь и нарушения контрольных значений КПУР. На основе входных данных в формате JSON модуль
        выполняет детерминированные расчёты, сравнивает показатели со среднерыночными значениями
        и формирует текстовое заключение с опорой на эталонные примеры от аналитиков ОРИКС.
    </div>
</div>
<hr class="orix-hr">
""", unsafe_allow_html=True)

st.markdown('<div class="orix-form-wrap">', unsafe_allow_html=True)

col_metric, col_period = st.columns([3, 1], gap="medium")
with col_metric:
    metric_choice = st.selectbox("Тип метрики", options=METRICS, format_func=lambda x: x[0], index=0, key="metric_select")
with col_period:
    st.text_input("Отчётный период", value="2025Q3", key="period_input")

col_json, col_file = st.columns(2, gap="medium")
with col_json:
    json_text = st.text_area(
        "Вставить JSON вручную", height=220,
        placeholder='{\n    "series": [\n        {"serie": "0", "label": "Мой банк", "value": 0.269},\n        {"serie": "1", "label": "Банк 1", "value": 0.004}\n    ],\n    "avg": 0.8231\n}',
        key="json_input",
    )
with col_file:
    uploaded_file = st.file_uploader("Или загрузить JSON-файл", type="json", key="file_input")

run_clicked = st.button("Запустить анализ", key="run_btn")
st.markdown("</div>", unsafe_allow_html=True)

if run_clicked:
    period = st.session_state.get("period_input", "2025Q3")
    _, selected_type = metric_choice

    raw_data = None
    if uploaded_file is not None:
        try:
            raw_data = json.load(uploaded_file)
        except json.JSONDecodeError as e:
            st.error(f"Невалидный JSON в файле: {e}"); st.stop()
    elif json_text and json_text.strip():
        try:
            raw_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            st.error(f"Невалидный JSON: {e}"); st.stop()
    else:
        st.warning("Вставьте JSON или загрузите файл."); st.stop()

    is_valid, errors = InputValidator().validate(raw_data)
    if not is_valid:
        st.error("Ошибки в данных:")
        for e in errors: st.write(f"— {e}")
        st.stop()

    if selected_type != MetricType.LOSS_SHARE.value:
        st.warning("В текущей версии реализована только метрика «Доля потерь в бизнес-индикаторе». Метрики 2–6 появятся в следующих спринтах.")
        st.stop()

    with st.spinner("Выполняется анализ..."):
        try:
            series_items = []
            for i, item in enumerate(raw_data.get("series", [])):
                kwargs = dict(serie=str(item.get("serie", i)), label=item.get("label", ""),
                              value=item.get("value"), rest=item.get("rest"))
                if "self" in item:
                    kwargs["self"] = item["self"]
                series_items.append(OrixSeriesItem(**kwargs))

            response = AnalysisPipeline().process_metric(
                GenerationRequest(
                    metric_type=selected_type, period=period, bank_id="my_bank",
                    data=OrixMetricInput(series=series_items, avg=raw_data.get("avg")),
                )
            )
        except ValueError as e:
            st.error(f"Ошибка обработки: {e}"); st.stop()
        except Exception as e:
            st.error(f"Внутренняя ошибка: {e}"); st.stop()

    calc = response.calculations
    diff = calc.difference_percent
    diff_class = "down" if diff < 0 else "up"
    diff_str = f"{'+'if diff > 0 else ''}{diff:.1f}%"

    st.markdown('<hr class="orix-hr">', unsafe_allow_html=True)
    st.markdown('<div class="orix-result-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="orix-section-label">Результат анализа</div>', unsafe_allow_html=True)

    if calc.position and calc.total_banks:
        st.markdown(f'<div class="orix-rank-pill">Позиция в рейтинге: {calc.position} место из {calc.total_banks} банков</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="orix-metrics-grid">
        <div class="orix-metric-card"><div class="orix-metric-card-label">Мой банк</div><div class="orix-metric-card-value">{calc.my_bank_value:.4f}</div></div>
        <div class="orix-metric-card"><div class="orix-metric-card-label">Среднее по кластеру</div><div class="orix-metric-card-value">{calc.cluster_avg_value:.4f}</div></div>
        <div class="orix-metric-card"><div class="orix-metric-card-label">Отклонение</div><div class="orix-metric-card-value {diff_class}">{diff_str}</div></div>
        <div class="orix-metric-card"><div class="orix-metric-card-label">Класс отклонения</div><div class="orix-metric-card-value" style="font-size:18px;padding-top:5px;">{calc.deviation_threshold}</div></div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div class="orix-verdict">
        <div class="orix-verdict-header">Аналитический вывод</div>
        <div class="orix-verdict-body">{response.verdict}</div>
    </div>""", unsafe_allow_html=True)

    q_pct = int(response.quality_score * 100)
    val_status = "Пройдена" if response.validation_passed else "Не пройдена"
    st.markdown(f"""
    <div class="orix-quality">
        <span>Оценка качества: <strong>{response.quality_score:.2f} ({q_pct}%)</strong></span>
        <span>Валидация: <strong>{val_status}</strong></span>
    </div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)