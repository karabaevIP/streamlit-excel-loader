import streamlit as st
import pandas as pd

# ---------- Настройки страницы ----------
st.set_page_config(page_title="Калькулятор молочных метрик", layout="wide")

# ---------- Базисные константы ----------
BASIS_FAT = 0.036
BASIS_PROT = 0.032
BASIS_FAT_PRICE = 0.038
FAT_SHARE = 0.52
PROT_SHARE = 0.48

MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

# ---------- Тексты подсказок ----------
HELP = {
    "weight":  "Масса принятого молока, кг (или в иных единицах — главное единообразие по году).",
    "price":   "Цена за единицу XX_з.в. при базисе 3.6% жира, руб.",
    "fat":     "Массовая доля жира, %. В формулах используется как доля (делится на 100).",
    "prot":    "Массовая доля белка, %. В формулах используется как доля (делится на 100).",
    "zv":      "XX_з.в. = (вес × жир_доля) / 0.036 — приведение объёма к базису 3.6% по жиру.",
    "stoim":   "XX_стоим = XX_з.в. × цена — стоимость в базисных единицах.",
    "bkg":     "XX_бкг = вес × бел_доля — масса белка, кг.",
    "bc":      "XX_бц (базисная цена). Если вес=0 → 0. Иначе: "
               "стоим / (вес × 0.52 / 0.038 × жир_доля + вес × 0.48 / 0.032 × бел_доля).",
    "bv":      "XX_бв. Если вес=0 → 0. Иначе: стоим / XX_бц.",
}


# ---------- Функция расчёта (векторизованная под DataFrame) ----------
def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Принимает DataFrame с колонками weight/price/fat/prot (в %),
    возвращает DataFrame со всеми метриками."""
    out = df.copy()
    fat = out["weight"] * 0 + out["fat"] / 100.0   # доля
    prot = out["weight"] * 0 + out["prot"] / 100.0

    out["XX_з.в."] = (out["weight"] * fat) / BASIS_FAT
    out["XX_стоим"] = out["XX_з.в."] * out["price"]
    out["XX_бкг"] = out["weight"] * prot

    denom = (out["weight"] * FAT_SHARE / BASIS_FAT_PRICE * fat
             + out["weight"] * PROT_SHARE / BASIS_PROT * prot)

    out["XX_бц"] = 0.0
    mask_w = out["weight"] != 0
    mask_d = denom != 0
    out.loc[mask_w & mask_d, "XX_бц"] = out.loc[mask_w, "XX_стоим"] / denom.loc[mask_w & mask_d]

    out["XX_бв"] = 0.0
    mask_bc = out["XX_бц"] != 0
    out.loc[mask_w & mask_bc, "XX_бв"] = out.loc[mask_w, "XX_стоим"] / out.loc[mask_w & mask_bc, "XX_бц"]

    return out


# ---------- Загрузка референсников ----------
@st.cache_data
def load_reference(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    required = {"Завод", "Код_контрагента", "Контрагент", "Тип_контрагента"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"В Excel не хватает столбцов: {missing}")
    for c in required:
        df[c] = df[c].astype(str).str.strip()
    return df.drop_duplicates(subset=list(required)).reset_index(drop=True)


def demo_reference() -> pd.DataFrame:
    return pd.DataFrame({
        "Завод": ["Завод-1", "Завод-1", "Завод-2", "Завод-2"],
        "Код_контрагента": ["К001", "К002", "К003", "К004"],
        "Контрагент": ["МолокоАгро", "Ферма №5", "Агрохолдинг Восток", "СК Племенной"],
        "Тип_контрагента": ["СНТ", "ЛПХ", "КФХ", "СНТ"],
    })


# ---------- Sidebar ----------
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
    st.caption("Базисы: жир 3.6%, белок 3.2%. Наведите на ⓘ у метрик — увидите формулы.")


# ---------- Основная форма: измерения ----------
st.title("Калькулятор производных метрик молока (помесячно)")

st.subheader("Базовые измерения")
col_dim1, col_dim2 = st.columns(2)

with col_dim1:
    factories = sorted(ref["Завод"].unique().tolist())
    factory = st.selectbox("Завод", options=factories, key="sel_factory")

with col_dim2:
    types = sorted(ref["Тип_контрагента"].unique().tolist())
    counterparty_type = st.selectbox("Тип контрагента", options=types, key="sel_type")

ref_filtered = ref[
    (ref["Завод"] == factory) & (ref["Тип_контрагента"] == counterparty_type)
]
if ref_filtered.empty:
    ref_filtered = ref
    st.warning("По выбранным заводу и типу контрагентов нет — показан общий список.")

options = [f"{r['Код_контрагента']} | {r['Контрагент']}" for _, r in ref_filtered.iterrows()]
selected = st.selectbox("Контрагент (код или имя)", options=options, key="sel_counter")
code, name = [s.strip() for s in selected.split("|", 1)]

c1, c2 = st.columns(2)
c1.text_input("Код контрагента", value=code, disabled=True)
c2.text_input("Наименование контрагента", value=name, disabled=True)


# ---------- Таблица помесячного ввода ----------
st.subheader("Базовые метрики по месяцам")
st.caption("Заполните вес, цену, жир и белок по каждому месяцу. Наведите на заголовок колонки — увидите подсказку.")

# Ключ хранения данных — привязан к контрагенту, чтобы при смене контрагента очищать таблицу
data_key = f"monthly_{factory}_{code}"

def empty_monthly_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Месяц": MONTHS,
        "weight": [0.0] * 12,
        "price":  [0.0] * 12,
        "fat":    [0.0] * 12,
        "prot":   [0.0] * 12,
    })

# Если сменился контрагент/завод — очищаем старые данные
last_key = st.session_state.get("_last_data_key")
if last_key != data_key:
    # Удаляем старый ключ data_editor, если был
    old_editor_key = f"editor_{last_key}" if last_key else None
    if old_editor_key and old_editor_key in st.session_state:
        del st.session_state[old_editor_key]
    st.session_state["_last_data_key"] = data_key

editor_key = f"editor_{data_key}"

column_config = {
    "Месяц":  st.column_config.TextColumn("Месяц", disabled=True, width="small"),
    "weight": st.column_config.NumberColumn("XX_вес",          min_value=0.0, step=0.01,  format="%.3f", help=HELP["weight"]),
    "price":  st.column_config.NumberColumn("XX_цена, базис 3.6%", min_value=0.0, step=0.01,  format="%.2f", help=HELP["price"]),
    "fat":    st.column_config.NumberColumn("XX_жир, %",       min_value=0.0, max_value=100.0, step=0.01, format="%.2f", help=HELP["fat"]),
    "prot":   st.column_config.NumberColumn("XX_бел, %",       min_value=0.0, max_value=100.0, step=0.01, format="%.2f", help=HELP["prot"]),
}

input_df = st.data_editor(
    empty_monthly_df() if data_key not in st.session_state else st.session_state[data_key],
    column_config=column_config,
    use_container_width=True,
    num_rows="fixed",
    key=editor_key,
    hide_index=True,
)
# Сохраняем актуальное состояние
st.session_state[data_key] = input_df


# ---------- Расчёт производных метрик ----------
result_df = calculate_metrics(input_df)

# Переименуем входные колонки для красивого вывода
rename_in = {
    "weight": "XX_вес",
    "price":  "XX_цена",
    "fat":    "XX_жир, %",
    "prot":   "XX_бел, %",
}
display_df = result_df.rename(columns=rename_in)

# Порядок колонок
cols_order = [
    "Месяц",
    "XX_вес", "XX_цена", "XX_жир, %", "XX_бел, %",
    "XX_з.в.", "XX_стоим", "XX_бкг", "XX_бц", "XX_бв",
]
display_df = display_df[cols_order]


# ---------- Итоговые карточки (сумма/среднее по году) ----------
st.subheader("Итоги по году")

total_weight = display_df["XX_вес"].sum()
total_zv     = display_df["XX_з.в."].sum()
total_stoim  = display_df["XX_стоим"].sum()
total_bkg    = display_df["XX_бкг"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Σ XX_вес",   f"{total_weight:,.3f}".replace(",", " "))
k2.metric("Σ XX_з.в.",  f"{total_zv:,.3f}".replace(",", " "))
k3.metric("Σ XX_стоим", f"{total_stoim:,.2f}".replace(",", " "))
k4.metric("Σ XX_бкг",   f"{total_bkg:,.3f}".replace(",", " "))


# ---------- Сводная таблица с подсказками ----------
st.subheader("Производные метрики по месяцам")

# Для производных метрик — отдельные tooltip'ы через st.dataframe с column_config
out_config = {
    "XX_вес":     st.column_config.NumberColumn("XX_вес",     format="%.3f", help=HELP["weight"]),
    "XX_цена":    st.column_config.NumberColumn("XX_цена",    format="%.2f", help=HELP["price"]),
    "XX_жир, %":  st.column_config.NumberColumn("XX_жир, %",  format="%.2f", help=HELP["fat"]),
    "XX_бел, %":  st.column_config.NumberColumn("XX_бел, %",  format="%.2f", help=HELP["prot"]),
    "XX_з.в.":    st.column_config.NumberColumn("XX_з.в.",    format="%.3f", help=HELP["zv"]),
    "XX_стоим":   st.column_config.NumberColumn("XX_стоим",   format="%.2f", help=HELP["stoim"]),
    "XX_бкг":     st.column_config.NumberColumn("XX_бкг",     format="%.3f", help=HELP["bkg"]),
    "XX_бц":      st.column_config.NumberColumn("XX_бц",      format="%.2f", help=HELP["bc"]),
    "XX_бв":      st.column_config.NumberColumn("XX_бв",      format="%.2f", help=HELP["bv"]),
}
st.dataframe(display_df, column_config=out_config, use_container_width=True, hide_index=True)


# ---------- Экспорт ----------
st.subheader("Экспорт")

# Добавляем измерения в итоговый CSV
export_df = display_df.copy()
export_df.insert(0, "Завод", factory)
export_df.insert(1, "Код_контрагента", code)
export_df.insert(2, "Контрагент", name)
export_df.insert(3, "Тип_контрагента", counterparty_type)

csv = export_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Скачать CSV (12 месяцев × все метрики)",
    data=csv,
    file_name=f"metrics_{code}_{factory}.csv",
    mime="text/csv",
)
