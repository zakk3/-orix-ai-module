import os, sys, json, base64
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.input_models import GenerationRequest, OrixMetricInput, OrixSeriesItem
from src.models.enums import MetricType
from src.core.pipeline import AnalysisPipeline
from src.core.validation.input_validator import InputValidator


LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "orix_logo.png")

# Список доступных метрик (название для UI + тип для pipeline)
METRICS = [
    ("Чистые потери к бизнес-индикатору",               MetricType.LOSS_SHARE.value),
    ("Уровень возмещения прямых потерь",                 MetricType.RECOVERY_LEVEL.value),
    ("Распределение по бакетам потерь",                  MetricType.LOSS_BUCKETS.value),
    ("Динамика чистых потерь за период",                 MetricType.DIRECT_LOSSES_DYNAMICS.value),
    ("Распределение прямых потерь по источникам риска",  MetricType.CONCENTRATION.value),
    ("Декомпозиция непрямых потерь",                     MetricType.KPUR_VIOLATION.value),
]



st.set_page_config(
    page_title="ОРИКС — Аналитика потерь",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Onest:wght@400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
    background: #ffffff !important;
    color: #0d1b2a !important;
}

[data-testid="collapsedControl"], [data-testid="stSidebar"],
section[data-testid="stSidebar"], #MainMenu, footer,
header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

.block-container {
    padding: 0 !important;
    max-width: 820px !important;
    margin: 0 auto !important;
}

.stApp > div:first-child { padding-top: 0 !important; }
section[data-testid="stMain"] { padding-top: 0 !important; background: #ffffff !important; }
.stMainBlockContainer { padding-top: 0 !important; }
div[class*="appview-container"] { background: #ffffff !important; }
.stApp { padding-top: 0 !important; }

.o-nav {
    display: flex; align-items: center;
    padding: 14px 0; background: transparent;
    margin-bottom: 0;
}
.o-nav-logo { display: flex; align-items: center; gap: 12px; }
.o-nav-logo img { height: 32px; width: auto; }
.o-nav-brand {
    font-family: 'Onest', sans-serif;
    font-size: 20px; font-weight: 700; color: #0d1b2a;
}

.o-hero { padding: 44px 0 32px; background: #ffffff; }
.o-hero-title {
    font-size: 34px; font-weight: 800; color: #0d1b2a;
    line-height: 1.2; letter-spacing: -0.8px; margin-bottom: 14px;
}
.o-hero-desc { font-size: 15px; color: #5a6980; line-height: 1.65; }

.o-divider { border: none; border-top: 1px solid #e0e6ef; margin: 0 0 24px 0; }

div[data-testid="stSelectbox"] label,
div[data-testid="stTextArea"] label,
div[data-testid="stFileUploader"] label {
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important; font-weight: 700 !important;
    color: #7a8fa8 !important; letter-spacing: 0.7px !important;
    text-transform: uppercase !important;
}

div[data-testid="stSelectbox"] > div > div {
    border: 1.5px solid #c8d8ea !important;
    border-radius: 8px !important;
    background: #ffffff !important;
    font-size: 14px !important; font-weight: 500 !important;
    color: #0d1b2a !important; min-height: 44px !important;
    box-shadow: none !important;
}
div[data-testid="stSelectbox"] > div > div:hover { border-color: #4f7fe8 !important; }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background: #ffffff !important; color: #0d1b2a !important; }

div[data-baseweb="popover"], ul[role="listbox"], div[role="listbox"] {
    background: #ffffff !important;
    border: 1.5px solid #c8d8ea !important;
    border-radius: 8px !important;
    box-shadow: 0 8px 24px rgba(13,27,42,0.1) !important;
}
li[role="option"], div[role="option"] {
    font-size: 14px !important; color: #0d1b2a !important;
    background: #ffffff !important; padding: 10px 16px !important;
}
li[role="option"]:hover, div[role="option"]:hover,
li[aria-selected="true"], div[aria-selected="true"] {
    background: #edf2ff !important; color: #4f7fe8 !important;
}

div[data-testid="stTextArea"] > div { background: #ffffff !important; border: none !important; }
div[data-testid="stTextArea"] textarea {
    border: 1.5px solid #c8d8ea !important;
    border-radius: 8px !important;
    background: #ffffff !important;
    font-family: 'Courier New', monospace !important;
    font-size: 12px !important; color: #0d1b2a !important;
    padding: 12px 14px !important; resize: none !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border-color: #4f7fe8 !important;
    box-shadow: 0 0 0 3px rgba(79,127,232,0.12) !important;
    outline: none !important;
}
div[data-testid="stTextArea"] [data-baseweb="textarea"],
div[data-testid="stTextArea"] [data-baseweb="base-input"] {
    background: #ffffff !important; border: none !important;
}

[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"] {
    border: 1.5px solid #c8d8ea !important;
    border-radius: 8px !important;
    background: #ffffff !important;
    padding: 20px 16px !important;
}
[data-testid="stFileUploader"] button {
    background: #4f7fe8 !important; color: #ffffff !important;
    border: none !important; border-radius: 6px !important;
    font-size: 0 !important; padding: 0 20px !important;
    min-height: 36px !important; min-width: 110px !important;
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
}
[data-testid="stFileUploader"] button::after {
    content: "Загрузить" !important; color: #ffffff !important;
    font-size: 13px !important; font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stFileUploader"] button > * { display: none !important; }
[data-testid="stFileUploader"] button:hover { background: #3a6bd4 !important; }
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] p,
[data-testid="stFileUploaderDropzoneInstructions"] * {
    color: #7a8fa8 !important; font-size: 12px !important; background: transparent !important;
}

div[data-testid="stButton"] > button {
    background: #4f7fe8 !important; color: #ffffff !important;
    border: none !important; border-radius: 8px !important;
    font-size: 14px !important; font-weight: 600 !important;
    padding: 12px 32px !important; margin-top: 8px !important;
    transition: all 0.15s ease !important;
    font-family: 'Inter', sans-serif !important;
}
div[data-testid="stButton"] > button:hover {
    background: #3a6bd4 !important; transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(79,127,232,0.3) !important;
}

.res-card {
    background: #ffffff;
    border: 1px solid #dde5f0;
    border-radius: 12px;
    padding: 28px 32px 32px;
    margin-top: 32px;
}
.res-title { font-size: 16px; font-weight: 700; color: #0d1b2a; margin-bottom: 4px; }
.res-sub {
    font-size: 12px; font-weight: 600; color: #7a8fa8;
    letter-spacing: 0.5px; margin-bottom: 8px;
}

.ai-box {
    background: #ffffff;
    border: 1px solid #dde5f0;
    border-left: 4px solid #4f7fe8;
    border-radius: 8px;
    padding: 20px 24px;
    margin-top: 24px;
}
.ai-lbl {
    font-size: 10px; font-weight: 700; color: #4f7fe8;
    letter-spacing: 0.9px; text-transform: uppercase; margin-bottom: 14px;
}
.ai-text { font-size: 15px; color: #1a2840; line-height: 1.72; }
.ai-text p { margin: 0 0 12px 0; }
.ai-text p:last-child { margin-bottom: 0; }

.val-fail { color: #c0392b; font-size: 13px; font-weight: 600; margin-top: 16px; }

div[data-testid="stAlert"] { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)


def get_logo_html() -> str:
    # Возвращаем логотип как base64 или SVG-заглушку если файл не найден
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" />'
    return """<svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="36" height="36" rx="8" fill="#4f7fe8"/>
      <path d="M11 18C11 14.134 14.134 11 18 11C21.866 11 25 14.134 25 18C25 21.866 21.866 25 18 25"
            stroke="white" stroke-width="2" stroke-linecap="round"/>
      <path d="M18 25C15.8 25 14 23.2 14 18" stroke="white" stroke-width="2" stroke-linecap="round"/>
    </svg>"""


def build_verdict_html(verdict: str) -> str:
    # Разбиваем текст вывода на абзацы и экранируем HTML-спецсимволы
    parts = []
    for para in verdict.strip().split("\n\n"):
        para = para.strip()
        if para:
            safe = (
                para
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            parts.append(f"<p>{safe}</p>")
    return "\n".join(parts)


# Навбар с логотипом
st.markdown(
    f'<div class="o-nav"><div class="o-nav-logo">'
    f'{get_logo_html()}'
    f'<span class="o-nav-brand">ОРИКС</span>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# Заголовок и описание модуля
st.markdown(
    '<div class="o-hero">'
    '<div class="o-hero-title">Автоматический анализ<br>операционных рисков</div>'
    '<div class="o-hero-desc">ИИ-модуль ОРИКС автоматически формирует развёрнутые аналитические выводы '
    'по ключевым показателям операционного риска банка. На основе входных данных в формате JSON модуль '
    'выполняет детерминированные расчёты, сравнивает показатели со среднерыночными значениями '
    'и формирует текстовое заключение с опорой на эталонные примеры от аналитиков ОРИКС.</div>'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown('<hr class="o-divider">', unsafe_allow_html=True)

# Форма ввода: выбор метрики и загрузка JSON
metric_choice = st.selectbox(
    "Тип метрики",
    options=METRICS,
    format_func=lambda x: x[0],
    index=0,
    key="metric_select",
)

col_json, col_file = st.columns(2, gap="medium")
with col_json:
    json_text = st.text_area(
        "Вставить JSON вручную",
        value="",
        height=210,
        key="json_input",
    )
with col_file:
    uploaded_file = st.file_uploader(
        "Или загрузить JSON-файл",
        type="json",
        key="file_input",
    )

run_clicked = st.button("Запустить анализ", key="run_btn")

if not run_clicked:
    st.stop()

# Парсинг JSON из файла или текстового поля
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

# Валидация структуры входных данных
is_valid, errors = InputValidator().validate(raw_data)
if not is_valid:
    st.error("Ошибки в данных:")
    for e in errors:
        st.write(f"— {e}")
    st.stop()

# Проверяем что выбранная метрика уже реализована
SUPPORTED_METRICS = {
    MetricType.LOSS_SHARE.value,
    MetricType.DIRECT_LOSSES_DYNAMICS.value,
    MetricType.LOSS_BUCKETS.value,
}
if selected_type not in SUPPORTED_METRICS:
    st.warning(
        "В текущей версии реализованы метрики «Чистые потери к бизнес-индикатору», "
        "«Динамика чистых потерь за период» и «Распределение по бакетам потерь»."
    )
    st.stop()

# Запуск pipeline: расчёты → LLM → валидация
with st.spinner("Выполняется анализ..."):
    try:
        series_items = []
        for i, item in enumerate(raw_data.get("series", [])):
            kwargs = dict(
                serie=str(item.get("serie", i)),
                label=item.get("label", ""),
                value=item.get("value"),
                rest=item.get("rest"),
            )
            if "self" in item:
                kwargs["self"] = item["self"]
            series_items.append(OrixSeriesItem(**kwargs))

        response = AnalysisPipeline().process_metric(
            GenerationRequest(
                metric_type=selected_type,
                period="2025Q3",
                bank_id="my_bank",
                data=OrixMetricInput(series=series_items, avg=raw_data.get("avg")),
            )
        )
    except ValueError as e:
        st.error(f"Ошибка обработки: {e}"); st.stop()
    except Exception as e:
        st.error(f"Внутренняя ошибка: {e}"); st.stop()

# Карточка результата — строим как единый HTML чтобы div-ы не ломались в Streamlit
metric_label = metric_choice[0]
verdict_paragraphs = build_verdict_html(response.verdict)

card_html = f"""
<div class="res-card">
    <div class="res-title">{metric_label}</div>
    <div class="res-sub">Аналитическое заключение</div>
    <div class="ai-box">
        <div class="ai-lbl">Аналитический вывод</div>
        <div class="ai-text">
            {verdict_paragraphs}
        </div>
    </div>
</div>
"""
st.markdown(card_html, unsafe_allow_html=True)

