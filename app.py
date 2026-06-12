# -*- coding: utf-8 -*-
"""
採用ダッシュボード / Dashboard tuyển dụng
Đọc dữ liệu từ Google Sheet (cột A–T) và hiển thị KPI, phễu, bảng 12 tháng.
Chưa cấu hình Google Sheet thì app tự chạy bằng DỮ LIỆU MẪU để xem trước.
"""

import datetime as dt
import random

import pandas as pd
import streamlit as st

# ============================================================
# 1) CẤU HÌNH — chỉnh ở đây, không cần sửa code phía dưới
# ============================================================

SHEET_NAME_DATA = "candidates"   # tên tab chứa dữ liệu ứng viên (cột A–T)
SHEET_NAME_TARGET = "targets"    # tên tab mục tiêu: 月 | 部門 | 職種 | 入社目標

# Email được coi là ADMIN (thấy thêm khu vực thao tác bot)
ADMIN_EMAILS = [
    "anh-h@dymvietnam.net",
]

# Tên cột trong Google Sheet (đúng theo header thật của bạn)
COL = {
    "date": "日付",
    "platform": "プラットフォーム",
    "name": "応募者名",
    "dept": "部門",
    "pos": "職種",
    "status": "ステータス",
    "dept_after": "面接後部門",
    "pos_after": "面接後職種",
}

# Quy tắc đếm theo trạng thái (cột K) — sửa lại nếu định nghĩa của bạn khác
# Ý tưởng: mỗi trạng thái cho biết ứng viên đã ĐI ĐẾN bước nào trong phễu
STAGE_OF_STATUS = {
    "履歴落ち":     "apply",      # chỉ tính vào 応募数
    "面接設定":     "interview",  # đã đến bước phỏng vấn
    "面接キャンセル": "apply",      # hẹn nhưng không PV -> không tính 面接数
    "面接落ち":     "interview",
    "内定":         "offer",
    "辞退":         "offer",      # từ chối sau khi có 内定
    "入社":         "hire",
}
STAGE_RANK = {"apply": 1, "interview": 2, "offer": 3, "hire": 4}

st.set_page_config(page_title="採用ダッシュボード", page_icon="📊", layout="wide")


# ============================================================
# 2) ĐỌC DỮ LIỆU
# ============================================================

@st.cache_data(ttl=300)  # cache 5 phút, bấm nút Làm mới để đọc lại ngay
def load_from_gsheet():
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet=SHEET_NAME_DATA)
    try:
        targets = conn.read(worksheet=SHEET_NAME_TARGET)
    except Exception:
        targets = pd.DataFrame(columns=["月", "部門", "職種", "入社目標"])
    return df, targets


def make_demo_data():
    """Dữ liệu mẫu để xem trước khi chưa nối Sheet."""
    random.seed(7)
    depts = {
        "事務代行": ["事務スタッフ"],
        "マーケティング": ["Sales", "Marketing"],
        "IT": ["Developer", "Tester"],
        "デザイン": ["Designer"],
        "管理部": ["人事"],
    }
    platforms = ["TopCV", "Vietnamworks", "ITviec", "Facebook", "紹介"]
    statuses = list(STAGE_OF_STATUS.keys())
    weights = [30, 12, 5, 18, 8, 4, 23]  # tỉ lệ xuất hiện của từng trạng thái

    rows, targets = [], []
    start = dt.date(2025, 7, 1)
    for i in range(12):
        month = (start + pd.DateOffset(months=i)).date()
        for dept, poss in depts.items():
            for pos in poss:
                targets.append({"月": month.strftime("%Y/%m"), "部門": dept,
                                "職種": pos, "入社目標": 2 if dept in ("IT", "マーケティング") else 1})
                for _ in range(random.randint(3, 14)):
                    d = month + dt.timedelta(days=random.randint(0, 27))
                    rows.append({
                        COL["date"]: d.strftime("%Y/%m/%d"),
                        COL["platform"]: random.choice(platforms),
                        COL["name"]: f"Demo {len(rows)+1}",
                        COL["dept"]: dept,
                        COL["pos"]: pos,
                        COL["status"]: random.choices(statuses, weights)[0],
                        COL["dept_after"]: "", COL["pos_after"]: "",
                    })
    return pd.DataFrame(rows), pd.DataFrame(targets)


def get_data():
    try:
        df, targets = load_from_gsheet()
        return df, targets, True
    except Exception:
        df, targets = make_demo_data()
        return df, targets, False


# ============================================================
# 3) TÍNH TOÁN
# ============================================================

def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[COL["date"]] = pd.to_datetime(df[COL["date"]], errors="coerce")
    df = df.dropna(subset=[COL["date"]])
    df["年"] = df[COL["date"]].dt.year.astype(str)
    df["月"] = df[COL["date"]].dt.strftime("%Y/%m")
    stage = df[COL["status"]].map(STAGE_OF_STATUS).fillna("apply")
    df["_rank"] = stage.map(STAGE_RANK)
    # Bộ phận/vị trí "hiệu lực": ưu tiên giá trị sau phỏng vấn nếu có
    df["_dept"] = df[COL["dept_after"]].replace("", pd.NA).fillna(df[COL["dept"]])
    df["_pos"] = df[COL["pos_after"]].replace("", pd.NA).fillna(df[COL["pos"]])
    return df


def funnel_counts(df: pd.DataFrame) -> dict:
    return {
        "応募数": len(df),
        "面接数": int((df["_rank"] >= 2).sum()),
        "内定数": int((df["_rank"] >= 3).sum()),
        "入社数": int((df["_rank"] >= 4).sum()),
    }


def rate(a, b):
    return f"{a / b * 100:.1f}%" if b else "–"


# ============================================================
# 4) GIAO DIỆN
# ============================================================

df_raw, df_target, connected = get_data()
df = prepare(df_raw)

st.title("📊 採用ダッシュボード")
st.caption("Dashboard theo dõi tuyển dụng — "
           + ("✅ đang đọc Google Sheet thật" if connected
              else "⚠️ CHƯA nối Google Sheet, đang hiển thị dữ liệu mẫu (xem README)"))
st.caption("定義: 面接率 = 面接数÷応募数 ・ 内定率 = 内定数÷面接数 ・ 入社率 = 入社数÷内定数")

# ----- phân quyền -----
user_email = getattr(st.user, "email", None) if hasattr(st, "user") else None
is_admin = user_email in ADMIN_EMAILS
with st.sidebar:
    st.markdown(f"**Đăng nhập:** {user_email or 'không xác định (chạy local)'}")
    st.markdown(f"**Quyền:** {'🔑 Admin' if is_admin else '👀 User (chỉ xem)'}")
    if st.button("🔄 Làm mới dữ liệu / 更新"):
        st.cache_data.clear()
        st.rerun()

# ----- bộ lọc -----
c1, c2, c3, c4, c5 = st.columns(5)
years = sorted(df["年"].unique(), reverse=True)
f_year = c1.selectbox("期間（年）/ Năm", ["すべて"] + years)
f_month = c2.selectbox("期間（月）/ Tháng", ["すべて"] + [f"{m:02d}" for m in range(1, 13)])
f_dept = c3.selectbox("部門 / Bộ phận", ["すべて"] + sorted(df["_dept"].dropna().unique()))
pos_options = sorted(df.loc[df["_dept"] == f_dept, "_pos"].dropna().unique()) \
    if f_dept != "すべて" else sorted(df["_pos"].dropna().unique())
f_pos = c4.selectbox("職種 / Vị trí", ["すべて"] + pos_options)
f_plat = c5.selectbox("プラットフォーム / Nền tảng",
                      ["すべて"] + sorted(df[COL["platform"]].dropna().replace("", pd.NA).dropna().unique()))

mask = pd.Series(True, index=df.index)
if f_year != "すべて":
    mask &= df["年"] == f_year
if f_month != "すべて":
    mask &= df["月"].str.endswith(f"/{f_month}")
if f_dept != "すべて":
    mask &= df["_dept"] == f_dept
if f_pos != "すべて":
    mask &= df["_pos"] == f_pos
if f_plat != "すべて":
    mask &= df[COL["platform"]] == f_plat
d = df[mask]

# ----- mục tiêu (lọc tương ứng) -----
tg = df_target.copy()
if not tg.empty:
    if f_year != "すべて":
        tg = tg[tg["月"].astype(str).str.startswith(f_year)]
    if f_month != "すべて":
        tg = tg[tg["月"].astype(str).str.endswith(f"/{f_month}")]
    if f_dept != "すべて":
        tg = tg[tg["部門"] == f_dept]
    if f_pos != "すべて":
        tg = tg[tg["職種"] == f_pos]
goal = int(pd.to_numeric(tg["入社目標"], errors="coerce").fillna(0).sum()) if not tg.empty else 0

# ----- KPI -----
f = funnel_counts(d)
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("応募数", f["応募数"])
k2.metric("面接数", f["面接数"])
k3.metric("内定数", f["内定数"])
k4.metric("入社数", f["入社数"],
          delta=f"目標 {goal} ・ {f['入社数']/goal*100:.0f}%" if goal else None)
k5.metric("面接率", rate(f["面接数"], f["応募数"]))
k6.metric("内定率", rate(f["内定数"], f["面接数"]))
k7.metric("入社率", rate(f["入社数"], f["内定数"]))

st.divider()

# ----- phễu + biểu đồ tháng -----
left, right = st.columns([1, 2])
with left:
    st.subheader("採用ファネル / Phễu")
    fun = pd.DataFrame({
        "段階": ["応募", "面接", "内定", "入社"],
        "人数": [f["応募数"], f["面接数"], f["内定数"], f["入社数"]],
    }).set_index("段階")
    st.bar_chart(fun, horizontal=True, color="#2D4FA1")
with right:
    st.subheader("月次推移 / Theo tháng")
    by_month = d.groupby("月").apply(
        lambda g: pd.Series(funnel_counts(g)), include_groups=False)
    if not by_month.empty:
        st.bar_chart(by_month[["応募数", "入社数"]], color=["#9FB4DE", "#2D4FA1"])
    else:
        st.info("Không có dữ liệu phù hợp bộ lọc")

# ----- bảng 12 tháng -----
st.subheader("全社 12ヶ月実績 / Bảng 12 tháng")
if not by_month.empty:
    t = by_month.copy()
    t["面接率"] = (t["面接数"] / t["応募数"] * 100).round(1).astype(str) + "%"
    t["内定率"] = (t["内定数"] / t["面接数"].replace(0, pd.NA) * 100).round(1).astype(str) + "%"
    t["入社率"] = (t["入社数"] / t["内定数"].replace(0, pd.NA) * 100).round(1).astype(str) + "%"
    if not df_target.empty:
        gt = df_target.groupby("月")["入社目標"].sum()
        t.insert(3, "入社目標", t.index.map(gt).fillna(0).astype(int))
    st.dataframe(t.replace("nan%", "–"), width="stretch")

# ----- bảng bộ phận-vị trí -----
st.subheader("部門・職種別 / Theo bộ phận – vị trí")
by_dp = d.groupby(["_dept", "_pos"]).apply(
    lambda g: pd.Series(funnel_counts(g)), include_groups=False)
if not by_dp.empty:
    by_dp["面接率"] = (by_dp["面接数"] / by_dp["応募数"] * 100).round(1).astype(str) + "%"
    by_dp["内定率"] = (by_dp["内定数"] / by_dp["面接数"].replace(0, pd.NA) * 100).round(1).astype(str) + "%"
    by_dp["入社率"] = (by_dp["入社数"] / by_dp["内定数"].replace(0, pd.NA) * 100).round(1).astype(str) + "%"
    by_dp.index.names = ["部門", "職種"]
    st.dataframe(by_dp.replace("nan%", "–"), width="stretch")
else:
    st.info("Không có dữ liệu phù hợp bộ lọc")

# ----- khu vực Admin -----
if is_admin:
    st.divider()
    st.subheader("🔑 Khu vực Admin")
    a1, a2, a3 = st.columns(3)
    if a1.button("🤖 Bot: Kéo CV mới về Sheet"):
        st.info("Chỗ này sẽ gọi webhook/bot xử lý CV (chưa nối).")
    if a2.button("✉️ Bot: Gửi mail kết quả"):
        st.info("Chỗ này sẽ gọi bot gửi mail (chưa nối).")
    if a3.button("📅 Bot: Tạo lịch Cybozu"):
        st.info("Chỗ này sẽ gọi API Cybozu (chưa nối).")
    st.caption("Các nút trên là chỗ chờ sẵn — khi build bot xong chỉ cần gắn webhook vào.")
