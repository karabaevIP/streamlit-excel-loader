import streamlit as st
import pandas as pd
import io

# ---------- Настройки страницы ----------
st.set_page_config(page_title="Калькулятор молочных метрик", layout="wide")

# ---------- Базисные константы ----------
BASIS_FAT = 0.036      # базис по жиру
BASIS_PROT = 0.032     # базис по белку (в формуле XX_бц)
FAT_SHARE = 0.52       # доля стоимости, приходящаяся на жир
PROT_SHARE = 0.48      # доля стоимости, приходящаяся на белок
# В формуле XX_бц используется 0.038 как базис жира для расчёта цены —
# это отдельный норматив, зафиксирован в формуле явно.
BASIS_FAT_PRICE = 0.038


# ---------- Функция расчёта производных метрик ----------
def calculate_metrics(weight: float, price: float, fat_pct: float, prot_pct: float) -> dict:
    """
    weight  — масса, кг (или тонны — единица не важна, главное единообразие)
    price   — цена за единицу XX_з.в., базис 3.6%
    fat_pct — жир, %
    prot_pct— белок, %
    """
    fat = fat_pct / 100.0
    prot = prot_pct / 100.0

    xx_zv = (weight * fat) / BASIS_FAT
    xx_stoim = xx_zv * price
    xx_bkg = weight * prot

    if weight == 0:
        xx_bc = 0.0
        xx_bv = 0.0
    else:
        denom = (weight * FAT_SHARE / BASIS_FAT_PRICE * fat
                 + weight * PROT_SHARE / BASIS_PROT * prot)
        xx_bc = xx_stoim / denom if denom != 0 else 0.0
        xx_bv = xx_stoim / xx_bkg if xx_bkg != 0 else 0.0

    return {
        "XX_вес": weight,
        "XX_цена": price,
        "XX_жир, %": fat_pct,
        "XX_бел, %": prot_pct,
        "XX_з.в.": xx_zv,
        "XX_стоим": xx_stoim,
        "XX_бкг": xx_bkg,
        "XX_бц": xx_bc,
        "XX_бв": xx_bv,
    }


# ---------- Загрузка референсников ----------
@st.cache_data
def load_reference(file) -> pd.DataFrame:
    """Читает Excel-файл с референсниками.
    Ожидаемые столбцы: Завод, Код_контрагента, Контрагент, Тип_контрагента
    """
    df = pd.read_excel(file)
    required = {"Завод", "Код_контрагента", "Контрагент", "Тип_контрагента"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"В Excel не хватает столбцов: {missing}")
    # Приведём к строкам и уберём дубликаты по комбинации
    for c in required:
        df[c] = df[c].astype(str).str.strip()
    return df.drop_duplicates(subset=list(required)).reset_index(drop=True)


def demo_reference() -> pd.DataFrame:
    """Демо-данные, если Excel не загружен — чтобы прототип работал из коробки."""
    return pd.DataFrame({
        "Завод": ["Завод-1", "Завод-1", "Завод-2", "Завод-2"],
        "Код_контрагента": ["К001", "К002", "К003", "К004"],
        "Контрагент": ["МолокоАгро", "Ферма №5", "Агрохолдинг Восток", "СК Племенной"],
        "Тип_контрагента": ["СНТ", "ЛПХ", "КФХ", "СНТ"],
    })


# ---------- Sidebar: загрузка Excel ----------
with st.sidebar:
    st.header("Справочники")
    uploaded = st.file_uploader(
        "Загрузите Excel со справочниками (Завод, Код, Контрагент, Тип)",
        type=["xlsx", "xls"],
    )
    if uploaded is not None:
        try:
            ref = load_reference(uploaded)
            st.success(f"Загружено строк: {len(ref)}")
        except Exception as e:
            st.error(f"Ошибка чтения файла: {e}")
            ref = demo_reference()
            st.warning("Используются демо-данные.")
    else:
        ref = demo_reference()
        st.info("Файл не загружен — используются демо-данные.")

    st.divider()
    st.caption("Формулы зафиксированы. Базисы: жир 3.6%, белок 3.2%")


# ---------- Основная форма ----------
st.title("Калькулятор производных метрик молока")

# --- Измерения ---
st.subheader("Базовые измерения")
col_dim1, col_dim2 = st.columns(2)

with col_dim1:
    factories = sorted(ref["Завод"].unique().tolist())
    factory = st.selectbox("Завод", options=factories)

with col_dim2:
    types = sorted(ref["Тип_контрагента"].unique().tolist())
    counterparty_type = st.selectbox("Тип контрагента", options=types)

# Единый селект контрагента: "Код | Наименование"
# Фильтруем по заводу и типу, чтобы список был релевантным
ref_filtered = ref[
    (ref["Завод"] == factory) & (ref["Тип_контрагента"] == counterparty_type)
]
if ref_filtered.empty:
    # Если по фильтру пусто — даём выбрать из всех, но предупреждаем
    ref_filtered = ref
    st.warning("По выбранным заводу и типу контрагентов нет — показан общий список.")

options = [
    f"{row['Код_контрагента']} | {row['Контрагент']}"
    for _, row in ref_filtered.iterrows()
]
selected = st.selectbox("Контрагент (код или имя)", options=options)

# Разбираем выбор обратно в код/имя
code, name = [s.strip() for s in selected.split("|", 1)]

# Показываем распознанные значения — пользователю спокойнее
c1, c2 = st.columns(2)
c1.text_input("Код контрагента", value=code, disabled=True)
c2.text_input("Наименование контрагента", value=name, disabled=True)


# --- Базовые метрики ---
st.subheader("Базовые метрики")
m1, m2, m3, m4 = st.columns(4)
with m1:
    weight = st.number_input("XX_вес", min_value=0.0, step=0.01, format="%.3f")
with m2:
    price = st.number_input("XX_цена, базис 3,6%", min_value=0.0, step=0.01, format="%.2f")
with m3:
    fat = st.number_input("XX_жир, %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f")
with m4:
    prot = st.number_input("XX_бел, %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f")


# ---------- Расчёт и вывод ----------
result = calculate_metrics(weight, price, fat, prot)

st.divider()
st.subheader("Производные метрики")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("XX_з.в.", f"{result['XX_з.в.']:,.3f}".replace(",", " "))
k2.metric("XX_стоим", f"{result['XX_стоим']:,.2f}".replace(",", " "))
k3.metric("XX_бкг", f"{result['XX_бкг']:,.3f}".replace(",", " "))
k4.metric("XX_бц", f"{result['XX_бц']:,.2f}".replace(",", " "))
k5.metric("XX_бв", f"{result['XX_бв']:,.2f}".replace(",", " "))


# ---------- Экспорт (задел под DWH) ----------
st.divider()
st.subheader("Экспорт записи")

# Собираем полную строку для DWH
row_for_dwh = {
    "Завод": factory,
    "Код_контрагента": code,
    "Контрагент": name,
    "Тип_контрагента": counterparty_type,
    **result,
}
df_out = pd.DataFrame([row_for_dwh])

st.dataframe(df_out, use_container_width=True)

csv = df_out.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Скачать CSV (задел под загрузку в DWH)",
    data=csv,
    file_name="metrics_row.csv",
    mime="text/csv",
)
