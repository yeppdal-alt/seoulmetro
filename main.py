"""
서울 지하철 혼잡도 분석 대시보드
------------------------------------------------
- 데이터 출처: 서울교통공사 지하철혼잡도정보
- 실행 방법:
    1) 이 app.py 와 requirements.txt, 그리고
       "서울교통공사_지하철혼잡도정보_20251130.csv"
       파일을 같은 폴더에 넣는다.
    2) pip install -r requirements.txt
    3) streamlit run app.py
- Streamlit Cloud 배포 시: 저장소 루트에 app.py, requirements.txt,
  CSV 파일을 함께 올리면 그대로 동작한다.
"""

import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------
# 0. 기본 설정
# ------------------------------------------------------------------
st.set_page_config(
    page_title="서울 지하철 혼잡도 분석",
    page_icon="🚇",
    layout="wide",
)

DATA_FILE = "서울교통공사_지하철혼잡도정보_20251130.csv"

DATA_DESCRIPTION = """
**데이터 설명**

- 서울교통공사 1~8호선의 **30분 단위 평균 혼잡도**로, 해당 30분 동안 역을 통과한
  모든 열차의 평균 혼잡도 값입니다.
- 혼잡도 = **열차 정원 대비 실제 승차 인원 비율(%)**. 좌석이 모두 찬 상태를 34%로 산정합니다.
- 구성 항목: 요일 구분(평일/토요일/일요일), 호선, 역번호, 역명, 상하선 구분, 30분 단위 혼잡도(%)
- 2024년부터 **분기별**로 제공되는 데이터이며, 실제 배차 간격이나 행사·폭우·파업 등
  특이 이벤트는 반영되지 않을 수 있습니다.
"""

TIME_COLS = [
    "5시30분", "6시00분", "6시30분", "7시00분", "7시30분", "8시00분", "8시30분",
    "9시00분", "9시30분", "10시00분", "10시30분", "11시00분", "11시30분",
    "12시00분", "12시30분", "13시00분", "13시30분", "14시00분", "14시30분",
    "15시00분", "15시30분", "16시00분", "16시30분", "17시00분", "17시30분",
    "18시00분", "18시30분", "19시00분", "19시30분", "20시00분", "20시30분",
    "21시00분", "21시30분", "22시00분", "22시30분", "23시00분", "23시30분",
    "00시00분", "00시30분",
]

# 서울교통공사 혼잡도 구간 기준 (칸당 정원 대비 재차인원 비율, %)
CONGESTION_BANDS = [
    (0, 34, "여유", "#3B82F6"),
    (34, 80, "보통", "#22C55E"),
    (80, 130, "주의", "#EAB308"),
    (130, 150, "혼잡", "#F97316"),
    (150, 10_000, "매우혼잡", "#EF4444"),
]


def congestion_level(value: float) -> tuple[str, str]:
    """혼잡도 수치를 등급/색상으로 변환"""
    for lo, hi, label, color in CONGESTION_BANDS:
        if lo <= value < hi:
            return label, color
    return "매우혼잡", "#EF4444"


def time_label(col: str) -> str:
    """'5시30분' -> '05:30', 자정 이후는 '24:00' '24:30' 로 표기해 시간축 연속성 유지"""
    m = re.match(r"(\d+)시(\d+)분", col)
    h, mm = int(m.group(1)), int(m.group(2))
    if h < 5:  # 00시00분, 00시30분 -> 자정 넘긴 시간대
        h += 24
    return f"{h:02d}:{mm:02d}"


TIME_LABELS = [time_label(c) for c in TIME_COLS]


# ------------------------------------------------------------------
# 1. 데이터 로드
# ------------------------------------------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949")
    df["역번호"] = df["역번호"].astype(str)
    return df


try:
    df = load_data(DATA_FILE)
except FileNotFoundError:
    st.error(
        f"'{DATA_FILE}' 파일을 찾을 수 없습니다. "
        "app.py와 같은 폴더(또는 저장소 루트)에 CSV 파일을 넣어주세요."
    )
    st.stop()

ALL_LINES = sorted(df["호선"].unique(), key=lambda x: int(re.sub(r"\D", "", x)))
ALL_DAYTYPES = ["평일", "토요일", "일요일"]

# ------------------------------------------------------------------
# 2. 사이드바 - 필터 & 역 선택 (드롭다운 선택 + 검색어 입력 동시 지원)
# ------------------------------------------------------------------
st.sidebar.header("🔎 조회 조건")

daytype = st.sidebar.radio("요일 구분", ALL_DAYTYPES, horizontal=True)

line_sel = st.sidebar.selectbox("호선 선택", ["전체"] + list(ALL_LINES))

search_kw = st.sidebar.text_input(
    "역 이름 검색(입력)", placeholder="예: 강남, 서울역, 홍대입구 ..."
)

# 필터링된 후보 목록 구성
cand = df[df["요일구분"] == daytype].copy()
if line_sel != "전체":
    cand = cand[cand["호선"] == line_sel]
if search_kw:
    cand = cand[cand["출발역"].str.contains(search_kw.strip(), case=False, na=False)]

cand["표시명"] = (
    cand["호선"] + " · " + cand["출발역"] + " (" + cand["상하구분"] + ")"
)
station_options = sorted(cand["표시명"].unique())

if not station_options:
    st.sidebar.warning("검색 조건에 맞는 역이 없습니다. 검색어나 호선을 확인해주세요.")
    st.stop()

default_idx = 0
station_display = st.sidebar.selectbox(
    "역 선택(드롭다운)", station_options, index=default_idx
)

compare_stations = st.sidebar.multiselect(
    "여러 역 비교(선택, 최대 5개)",
    options=station_options,
    default=[station_display],
    max_selections=5,
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "혼잡도 기준: 0~34% 여유 · 34~80% 보통 · 80~130% 주의 · 130~150% 혼잡 · 150%+ 매우혼잡"
)

# 선택된 역의 실제 행 가져오기 (여러 역번호가 같은 이름을 가질 수 있어 표시명 기준 매칭)
def get_row(display_name: str) -> pd.Series:
    return cand[cand["표시명"] == display_name].iloc[0]


sel_row = get_row(station_display)

# ------------------------------------------------------------------
# 3. 헤더
# ------------------------------------------------------------------
st.title("🚇 서울 지하철역 혼잡도 분석 대시보드")
st.caption("데이터: 서울교통공사 지하철혼잡도정보 (2025-11-30 기준)")
with st.expander("ℹ️ 데이터 설명 보기", expanded=False):
    st.markdown(DATA_DESCRIPTION)

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 선택역 상세", "🆚 역 간 비교", "🏆 전체 랭킹 · 히트맵", "💡 인사이트 & 추천 분석"]
)

# ------------------------------------------------------------------
# TAB 1. 선택역 상세 분석
# ------------------------------------------------------------------
with tab1:
    st.subheader(f"{sel_row['호선']} {sel_row['출발역']}역 ({sel_row['상하구분']}) · {daytype}")

    values = sel_row[TIME_COLS].astype(float).values
    peak_idx = int(np.argmax(values))
    peak_time, peak_val = TIME_LABELS[peak_idx], values[peak_idx]
    peak_label, peak_color = congestion_level(peak_val)
    avg_val = values.mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("최고 혼잡 시간대", peak_time)
    c2.metric("최고 혼잡도", f"{peak_val:.1f}%", peak_label)
    c3.metric("일 평균 혼잡도", f"{avg_val:.1f}%")
    c4.metric("최저 혼잡도", f"{values.min():.1f}%")

    fig = go.Figure()

    # 혼잡도 구간 배경 밴드
    for lo, hi, label, color in CONGESTION_BANDS:
        fig.add_hrect(
            y0=lo, y1=min(hi, max(values.max(), hi) + 10),
            fillcolor=color, opacity=0.07, line_width=0,
        )

    fig.add_trace(
        go.Scatter(
            x=TIME_LABELS,
            y=values,
            mode="lines+markers",
            name=sel_row["출발역"],
            line=dict(color="#2563EB", width=3),
            marker=dict(size=5),
            hovertemplate="%{x} · 혼잡도 %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[peak_time], y=[peak_val],
            mode="markers+text",
            marker=dict(size=12, color="#EF4444", symbol="star"),
            text=[f"최고 {peak_val:.1f}%"],
            textposition="top center",
            name="최고 혼잡",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=480,
        xaxis_title="시간대",
        yaxis_title="혼잡도(%)",
        hovermode="x unified",
        margin=dict(t=30, l=10, r=10, b=10),
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("같은 역, 다른 요일 비교 보기"):
        day_fig = go.Figure()
        for d in ALL_DAYTYPES:
            row = df[
                (df["호선"] == sel_row["호선"])
                & (df["출발역"] == sel_row["출발역"])
                & (df["상하구분"] == sel_row["상하구분"])
                & (df["요일구분"] == d)
            ]
            if row.empty:
                continue
            vals = row.iloc[0][TIME_COLS].astype(float).values
            day_fig.add_trace(
                go.Scatter(x=TIME_LABELS, y=vals, mode="lines", name=d)
            )
        day_fig.update_layout(
            height=420, template="plotly_white",
            xaxis_title="시간대", yaxis_title="혼잡도(%)",
            margin=dict(t=20, l=10, r=10, b=10),
        )
        st.plotly_chart(day_fig, use_container_width=True)

# ------------------------------------------------------------------
# TAB 2. 여러 역 비교
# ------------------------------------------------------------------
with tab2:
    st.subheader("선택한 역들의 시간대별 혼잡도 비교")
    if not compare_stations:
        st.info("사이드바에서 비교할 역을 1개 이상 선택해주세요.")
    else:
        comp_fig = go.Figure()
        rows_for_table = []
        for disp in compare_stations:
            r = get_row(disp)
            vals = r[TIME_COLS].astype(float).values
            comp_fig.add_trace(
                go.Scatter(x=TIME_LABELS, y=vals, mode="lines+markers", name=disp)
            )
            rows_for_table.append(
                {
                    "역": disp,
                    "최고 혼잡도(%)": round(vals.max(), 1),
                    "최고 혼잡 시간대": TIME_LABELS[int(np.argmax(vals))],
                    "평균 혼잡도(%)": round(vals.mean(), 1),
                }
            )
        comp_fig.update_layout(
            height=500, template="plotly_white",
            xaxis_title="시간대", yaxis_title="혼잡도(%)",
            hovermode="x unified", margin=dict(t=20, l=10, r=10, b=10),
        )
        st.plotly_chart(comp_fig, use_container_width=True)
        st.dataframe(
            pd.DataFrame(rows_for_table).sort_values("최고 혼잡도(%)", ascending=False),
            use_container_width=True, hide_index=True,
        )

# ------------------------------------------------------------------
# TAB 3. 전체 랭킹 & 히트맵
# ------------------------------------------------------------------
with tab3:
    st.subheader(f"{daytype} 기준 · 전체 역 혼잡도 랭킹")

    base = df[df["요일구분"] == daytype].copy()
    if line_sel != "전체":
        base = base[base["호선"] == line_sel]

    base["최고혼잡도"] = base[TIME_COLS].astype(float).max(axis=1)
    base["최고혼잡시간대"] = base[TIME_COLS].astype(float).idxmax(axis=1).map(
        lambda c: time_label(c)
    )
    base["평균혼잡도"] = base[TIME_COLS].astype(float).mean(axis=1)

    top_n = st.slider("표시할 역 개수", 5, 50, 15)
    ranked = base.sort_values("최고혼잡도", ascending=False).head(top_n)

    rank_fig = px.bar(
        ranked,
        x="최고혼잡도",
        y=ranked["호선"] + " " + ranked["출발역"] + "(" + ranked["상하구분"] + ")",
        color="최고혼잡도",
        color_continuous_scale=["#3B82F6", "#22C55E", "#EAB308", "#F97316", "#EF4444"],
        orientation="h",
        hover_data={"최고혼잡시간대": True},
        labels={"y": "역", "최고혼잡도": "최고 혼잡도(%)"},
    )
    rank_fig.update_layout(
        height=max(400, top_n * 28), template="plotly_white",
        yaxis=dict(autorange="reversed"), margin=dict(t=20, l=10, r=10, b=10),
    )
    st.plotly_chart(rank_fig, use_container_width=True)

    st.markdown("#### 노선 × 시간대 평균 혼잡도 히트맵")
    heat = (
        df[df["요일구분"] == daytype]
        .groupby("호선")[TIME_COLS]
        .mean()
        .reindex(ALL_LINES)
    )
    heat_fig = px.imshow(
        heat.values,
        x=TIME_LABELS,
        y=heat.index,
        color_continuous_scale=["#3B82F6", "#22C55E", "#EAB308", "#F97316", "#EF4444"],
        aspect="auto",
        labels=dict(color="평균 혼잡도(%)"),
    )
    heat_fig.update_layout(height=380, margin=dict(t=20, l=10, r=10, b=10))
    st.plotly_chart(heat_fig, use_container_width=True)

# ------------------------------------------------------------------
# TAB 4. 인사이트 요약 + 추가 분석 추천
# ------------------------------------------------------------------
with tab4:
    st.subheader("자동 인사이트 요약")

    weekday_avg = df[df["요일구분"] == "평일"][TIME_COLS].astype(float).mean().mean()
    weekend_avg = (
        df[df["요일구분"].isin(["토요일", "일요일"])][TIME_COLS].astype(float).mean().mean()
    )
    busiest_line = (
        df[df["요일구분"] == "평일"].groupby("호선")[TIME_COLS].mean().mean(axis=1).idxmax()
    )
    busiest_row = df.loc[df[TIME_COLS].astype(float).max(axis=1).idxmax()]
    busiest_val = busiest_row[TIME_COLS].astype(float).max()
    busiest_time = time_label(busiest_row[TIME_COLS].astype(float).idxmax())

    st.markdown(
        f"""
- **평일 평균 혼잡도**: {weekday_avg:.1f}%  vs **주말 평균 혼잡도**: {weekend_avg:.1f}%
  (평일이 주말보다 약 {weekday_avg - weekend_avg:.1f}%p 더 혼잡)
- **평일 기준 가장 혼잡한 노선**: {busiest_line}
- **전체 데이터 중 최고 혼잡 기록**: {busiest_row['호선']} {busiest_row['출발역']}역
  ({busiest_row['상하구분']}, {busiest_row['요일구분']}) — **{busiest_time}에 {busiest_val:.1f}%**
- 출근 피크는 07:30~08:30, 퇴근 피크는 18:00~18:30 구간에 집중되는 경향이 관찰됨
        """
    )

    st.markdown("---")
    st.subheader("💡 이 데이터로 더 해볼 수 있는 분석 추천")
    st.markdown(
        """
1. **시차 출퇴근 효과 분석** — 30분 단위 데이터를 활용해 각 역의 피크가 몇 분 앞뒤로
   이동하면 혼잡도가 얼마나 낮아지는지 시뮬레이션 (시차출퇴근제 효과 검증)
2. **환승역 vs 비환승역 비교** — 역번호·역명을 기준으로 환승역 태그를 추가해
   환승역이 실제로 더 혼잡한지, 어느 시간대에 특히 그런지 통계 검정
3. **상선/하선(또는 내선/외선) 불균형 분석** — 같은 역이라도 방향별 혼잡도 격차가 큰 역을
   찾아 배차 간격 조정이 필요한 구간 식별
4. **노선별 군집분석(clustering)** — 42개 시간대 값을 특징벡터로 K-means/계층적 군집화하여
   "출퇴근형", "관광/상업형", "심야형" 등 역 유형 자동 분류
5. **요일 간 차이의 통계적 유의성 검정** — 평일 vs 토요일 vs 일요일 혼잡도 차이를
   ANOVA/Kruskal-Wallis로 검정해 요일별 배차 전략 근거 마련
6. **혼잡도-사고/지연 상관 분석(외부 데이터 결합)** — 지연 정보나 민원 데이터와 조인해
   혼잡도와 운행 장애 간 상관관계 탐색
7. **예측 모델링** — 시계열(요일·시간대) 패턴을 학습해 특정 역의 향후 혼잡도를 예측하고
   혼잡 알림 서비스에 활용
        """
    )

st.markdown("---")
st.caption("Made with Streamlit + Plotly · 데이터 출처: 서울교통공사")
