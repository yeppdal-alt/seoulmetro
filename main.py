# -*- coding: utf-8 -*-
"""
서울교통공사 역별 승하차인원 대시보드
데이터: 공공데이터포털 '서울교통공사_역별승하차인원' (B553766/psgr)
       https://www.data.go.kr/data/15143845/openapi.do

Streamlit Cloud 배포 방법
1) GitHub 저장소에 이 app.py 와 requirements.txt 를 올린다.
2) https://share.streamlit.io 에서 New app → 저장소 선택 → Main file: app.py
3) 앱이 뜨면 좌측 사이드바에 공공데이터포털에서 발급받은 서비스키(디코딩 키)를 입력한다.
   (App settings → Secrets 에 SEOUL_METRO_API_KEY = "발급받은키" 로 저장해두면 매번 입력하지 않아도 된다)

※ 주의: 이 API는 공식 문서에 정확한 응답 필드명이 공개돼 있지 않아(스웨거 UI가 자바스크립트로만
렌더링됨), 아래 코드는 응답 JSON을 자동으로 분석해서 '역명/날짜/시간/승차/하차'로 보이는 컬럼을
스스로 찾아 매핑한다. 만약 자동 매핑이 틀리면 사이드바의 '컬럼 직접 지정'에서 손으로 골라주면 된다.
데이터는 최근 1주일치만 제공된다.
"""

import re
import io
import json
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

API_BASE = "https://apis.data.go.kr/B553766/psgr/getStationPassengerList"

# 참고용 인기 역 목록 (선택 + 직접입력 겸용으로 사용)
POPULAR_STATIONS = [
    "강남", "홍대입구", "잠실", "신촌", "건대입구", "사당", "서울역",
    "종로3가", "왕십리", "선릉", "고속터미널", "역삼", "이수", "구로디지털단지",
]

st.set_page_config(page_title="서울 지하철 역별 승하차인원 대시보드", layout="wide")


# ----------------------------------------------------------------------------
# API 호출
# ----------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_data(service_key: str, station: str, use_date: str, num_of_rows: int = 1000):
    """공공데이터포털 API 호출. 실패 시 (None, 에러메시지) 반환."""
    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": num_of_rows,
        "resultType": "json",
        # API에서 요구하는 파라미터명이 다를 수 있어 자주 쓰이는 이름들을 함께 전송
        "STATN_NM": station,
        "stinNm": station,
        "USE_YMD": use_date.replace("-", ""),
        "useYmd": use_date.replace("-", ""),
    }
    try:
        resp = requests.get(API_BASE, params=params, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"API 요청 실패: {e}"

    text = resp.text.strip()

    # JSON 파싱 시도
    try:
        data = resp.json()
        return _extract_items(data), None
    except (ValueError, json.JSONDecodeError):
        pass

    # XML 로 응답이 오는 경우 대비
    try:
        import xmltodict

        data = xmltodict.parse(text)
        return _extract_items(data), None
    except Exception:
        return None, f"응답을 해석할 수 없습니다. 원본 응답 일부:\n{text[:500]}"


def _extract_items(data):
    """API 응답 구조가 제각각이어도 리스트(dict의 리스트)를 최대한 찾아서 반환."""
    if data is None:
        return []

    def find_list(obj):
        if isinstance(obj, list):
            if len(obj) == 0 or isinstance(obj[0], dict):
                return obj
        if isinstance(obj, dict):
            # 흔한 키 우선 탐색
            for key in ["item", "items", "row", "rows", "data", "list"]:
                if key in obj:
                    found = find_list(obj[key])
                    if found:
                        return found
            for v in obj.values():
                found = find_list(v)
                if found:
                    return found
        return None

    items = find_list(data)
    if items is None:
        return []
    if isinstance(items, dict):
        items = [items]
    return items


# ----------------------------------------------------------------------------
# 컬럼 자동 감지
# ----------------------------------------------------------------------------
COLUMN_KEYWORDS = {
    "station": ["역명", "역이름", "stin", "statn", "station", "역"],
    "date": ["일자", "날짜", "ymd", "date", "통행일"],
    "time": ["시간", "hh", "tm", "hour", "시간대"],
    "boarding": ["승차", "탑승", "ride", "geton", "board", "in"],
    "alighting": ["하차", "내림", "alight", "getoff", "off"],
    "line": ["호선", "노선", "line"],
    "card_type": ["교통카드", "card"],
}


def guess_columns(columns):
    guessed = {}
    for role, keywords in COLUMN_KEYWORDS.items():
        best = None
        for col in columns:
            low = str(col).lower()
            if any(kw.lower() in low for kw in keywords):
                best = col
                break
        guessed[role] = best
    return guessed


# ----------------------------------------------------------------------------
# 사이드바 - 입력
# ----------------------------------------------------------------------------
st.sidebar.title("🚇 조회 설정")

default_key = st.secrets.get("SEOUL_METRO_API_KEY", "") if hasattr(st, "secrets") else ""
service_key = st.sidebar.text_input(
    "공공데이터포털 서비스키 (Decoding Key)", value=default_key, type="password"
)

st.sidebar.markdown("**지하철역 선택**")
picked = st.sidebar.selectbox("자주 찾는 역에서 선택", ["직접 입력"] + POPULAR_STATIONS)
if picked == "직접 입력":
    station_name = st.sidebar.text_input("역 이름 직접 입력", value="강남")
else:
    station_name = picked
    manual = st.sidebar.text_input("다른 이름으로 입력하려면 여기에 (비워두면 위 선택값 사용)", value="")
    if manual.strip():
        station_name = manual.strip()

use_date = st.sidebar.date_input(
    "조회 날짜 (API는 최근 1주일 데이터만 제공)",
    value=date.today() - timedelta(days=1),
    max_value=date.today(),
)

run = st.sidebar.button("조회하기", type="primary", use_container_width=True)

with st.sidebar.expander("⚙️ 컬럼 직접 지정 (자동 인식이 틀렸을 때)"):
    st.caption("조회 후 이 곳에서 실제 컬럼명으로 다시 지정할 수 있습니다.")
    override_station = st.text_input("역명 컬럼", value="", key="ov_station")
    override_date = st.text_input("날짜 컬럼", value="", key="ov_date")
    override_time = st.text_input("시간 컬럼", value="", key="ov_time")
    override_board = st.text_input("승차 컬럼", value="", key="ov_board")
    override_alight = st.text_input("하차 컬럼", value="", key="ov_alight")


st.title("서울 지하철 역별 승하차인원 대시보드")
st.caption("데이터 출처: 공공데이터포털 서울교통공사_역별승하차인원 (B553766/psgr)")

if not service_key:
    st.info("좌측 사이드바에 공공데이터포털에서 발급받은 서비스키를 입력한 뒤 '조회하기'를 눌러주세요.")
    st.stop()

if not run and "df" not in st.session_state:
    st.info("좌측 사이드바에서 역과 날짜를 선택하고 '조회하기'를 눌러주세요.")
    st.stop()

if run:
    with st.spinner(f"'{station_name}' 역 데이터를 불러오는 중..."):
        items, err = fetch_data(service_key, station_name, str(use_date))
    if err:
        st.error(err)
        st.stop()
    if not items:
        st.warning("조회된 데이터가 없습니다. 역 이름/날짜를 확인하거나, API 요청 파라미터명이 실제 스펙과 다를 수 있습니다.")
        st.stop()
    st.session_state["df"] = pd.json_normalize(items)

df = st.session_state.get("df")
if df is None or df.empty:
    st.stop()

# ----------------------------------------------------------------------------
# 컬럼 매핑 (자동 감지 + 수동 오버라이드)
# ----------------------------------------------------------------------------
guessed = guess_columns(df.columns)

col_station = override_station or guessed["station"]
col_date = override_date or guessed["date"]
col_time = override_time or guessed["time"]
col_board = override_board or guessed["boarding"]
col_alight = override_alight or guessed["alighting"]
col_line = guessed["line"]

# 숫자형 변환
for c in [col_board, col_alight]:
    if c and c in df.columns:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

# ----------------------------------------------------------------------------
# KPI
# ----------------------------------------------------------------------------
total_board = df[col_board].sum() if col_board and col_board in df.columns else None
total_alight = df[col_alight].sum() if col_alight and col_alight in df.columns else None

k1, k2, k3, k4 = st.columns(4)
k1.metric("조회 역", station_name)
k2.metric("조회 일자", str(use_date))
k3.metric("총 승차인원", f"{int(total_board):,}명" if total_board is not None else "N/A")
k4.metric("총 하차인원", f"{int(total_alight):,}명" if total_alight is not None else "N/A")

if total_board is not None and total_alight is not None:
    net = total_board - total_alight
    st.caption(f"순유입(승차-하차): {int(net):+,}명")

st.divider()

# ----------------------------------------------------------------------------
# 그래프 (Plotly)
# ----------------------------------------------------------------------------
x_col = col_time if col_time and col_time in df.columns else (
    col_date if col_date and col_date in df.columns else None
)

tab1, tab2, tab3, tab4 = st.tabs(["시간대별 추이", "승차 vs 하차 비교", "누적 비율", "원본 데이터"])

with tab1:
    if x_col and (col_board or col_alight):
        plot_df = df.copy()
        if x_col in plot_df.columns:
            plot_df = plot_df.sort_values(x_col)
        fig = go.Figure()
        if col_board and col_board in plot_df.columns:
            fig.add_trace(go.Scatter(x=plot_df[x_col], y=plot_df[col_board],
                                      mode="lines+markers", name="승차", line=dict(color="#1f77b4")))
        if col_alight and col_alight in plot_df.columns:
            fig.add_trace(go.Scatter(x=plot_df[x_col], y=plot_df[col_alight],
                                      mode="lines+markers", name="하차", line=dict(color="#ff7f0e")))
        fig.update_layout(title=f"{station_name}역 시간대별 승하차 추이", xaxis_title=x_col,
                           yaxis_title="인원 수", hovermode="x unified", legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("시간/날짜 컬럼을 자동으로 찾지 못했습니다. 사이드바의 '컬럼 직접 지정'에서 지정해주세요.")

with tab2:
    if x_col and col_board and col_alight:
        plot_df = df.sort_values(x_col) if x_col in df.columns else df
        fig2 = go.Figure(data=[
            go.Bar(name="승차", x=plot_df[x_col], y=plot_df[col_board], marker_color="#1f77b4"),
            go.Bar(name="하차", x=plot_df[x_col], y=plot_df[col_alight], marker_color="#ff7f0e"),
        ])
        fig2.update_layout(barmode="group", title=f"{station_name}역 승차/하차 비교",
                            xaxis_title=x_col, yaxis_title="인원 수")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("승차/하차 컬럼을 자동으로 찾지 못했습니다. 사이드바의 '컬럼 직접 지정'에서 지정해주세요.")

with tab3:
    if total_board is not None and total_alight is not None:
        fig3 = px.pie(
            names=["승차", "하차"],
            values=[total_board, total_alight],
            hole=0.5,
            color_discrete_sequence=["#1f77b4", "#ff7f0e"],
            title=f"{station_name}역 승차/하차 비율",
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("승차/하차 합계를 계산할 수 없습니다.")

with tab4:
    st.write("자동 인식된 컬럼:", {
        "역명": col_station, "날짜": col_date, "시간": col_time,
        "승차": col_board, "하차": col_alight, "호선": col_line,
    })
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("CSV로 다운로드", data=csv, file_name=f"{station_name}_{use_date}.csv", mime="text/csv")
