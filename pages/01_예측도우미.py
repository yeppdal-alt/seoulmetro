# -*- coding: utf-8 -*-
"""
예측 도우미 페이지 (pages/00_예측도우미.py)
- 2025년 승하차 통계 + 혼잡도 데이터를 요일별로 분석하고,
  Upstage Solar(solar-open2) AI가 "어느 요일에 휴가를 내면 좋을지" 팁을 준다.
"""
from core import *   # 공통 모듈 (데이터 로더, 스타일, Solar API 등)

page_setup("예측 도우미 · 서울교통공사 대시보드", "🔮")

st.markdown("## 🔮 휴가 요일 추천 AI")
st.page_link("main.py", label="⬅️ 메인 대시보드로 돌아가기")

st.markdown(
    """
    <div class="hero">
      <div class="hero-title">🔮 어느 요일에 휴가를 낼까?</div>
      <div class="hero-sub">자주 이용하는 역의 요일별 이용 패턴과 혼잡도를 분석해,
      지하철이 한산한 '휴가 내기 좋은 요일'을 AI가 추천해 드립니다</div>
    </div>
    """,
    unsafe_allow_html=True,
)

keys = get_keys()
with st.spinner("역 목록 로딩 중..."):
    stations, _, _ = get_stations(keys)

# ── 1) 자주 이용하는 역 선택 ──
if stations:
    default_idx = stations.index("강남") if "강남" in stations else 0
    station = st.selectbox("자주 이용하는 역", stations, index=default_idx)
else:
    station = st.text_input("자주 이용하는 역 이름", value="강남")

# ── 2) 2025년 통계에서 요일별 평균 이용객 계산 ──
cmin, cmax = csv_date_range()
if not cmin:
    st.warning("2025년 승하차 통계 파일을 찾을 수 없어 요일 분석을 할 수 없습니다.")
    st.stop()

with st.spinner("요일별 이용 패턴 분석 중..."):
    all_dates = tuple(pd.date_range(cmin, cmax).strftime("%Y%m%d"))
    df = load_csv_period(all_dates, station)

if df.empty:
    st.warning(f"'{station}' 역의 2025년 데이터를 찾지 못했습니다. 다른 역을 선택해 주세요.")
    st.stop()

# 하루 합계 → 요일별 평균
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
daily = df.groupby("날짜", as_index=False)["합계"].sum()
daily["요일"] = pd.to_datetime(daily["날짜"], format="%Y%m%d").dt.dayofweek.map(
    dict(enumerate(WEEKDAYS)))
wk = (daily.groupby("요일")["합계"].mean().reindex(WEEKDAYS)
      .round().astype(int).reset_index())
wk.columns = ["요일", "평균 이용객"]

# 평일(월~금) 중 가장 한산한 요일 찾기
weekday_only = wk[wk["요일"].isin(WEEKDAYS[:5])]
best_day = weekday_only.loc[weekday_only["평균 이용객"].idxmin(), "요일"]
worst_day = weekday_only.loc[weekday_only["평균 이용객"].idxmax(), "요일"]

c1, c2 = st.columns(2)
c1.metric("😌 평일 중 가장 한산한 요일", f"{best_day}요일",
          help="2025년 하루 평균 이용객이 가장 적은 평일")
c2.metric("😵 평일 중 가장 붐비는 요일", f"{worst_day}요일",
          help="2025년 하루 평균 이용객이 가장 많은 평일")

# 요일별 평균 이용객 그래프 (한산한 요일 강조)
st.subheader(f"📊 {station}역 요일별 하루 평균 이용객 (2025년)")
wk["구분"] = wk["요일"].apply(lambda d: "가장 한산한 평일" if d == best_day else "그 외")
fig = px.bar(wk, x="요일", y="평균 이용객", color="구분",
             template=PLOTLY_TEMPLATE,
             color_discrete_map={"가장 한산한 평일": "#00A84D", "그 외": "#C9DCF0"},
             category_orders={"요일": WEEKDAYS})
fig.update_layout(height=380, margin=dict(t=20, b=10), showlegend=False)
show_chart(fig)

# ── 3) 혼잡도 요일 요약 (평일/토/일) ──
busy_summary = ""
busy_df, _busy_err = load_congestion(keys["busy"], station)
if busy_df is not None and not busy_df.empty:
    bsel = filter_by_station(busy_df, station)
    tcols = detect_time_cols(bsel) if not bsel.empty else []
    c_dow = find_col(bsel.columns, ["DOW", "요일"]) if not bsel.empty else None
    if tcols and c_dow:
        tmp = bsel.copy()
        tmp["_평균"] = tmp[tcols].apply(to_num).mean(axis=1)
        dow_avg = tmp.groupby(c_dow)["_평균"].mean().round(1)
        busy_summary = ", ".join(f"{k} {v}%" for k, v in dow_avg.items())
        st.caption(f"🚇 요일구분별 평균 혼잡도: {busy_summary} "
                   "(출처: 서울교통공사 30분 단위 평균, 좌석 만석 = 34%)")

# ── 4) Solar AI에게 휴가 요일 추천 받기 ──
st.subheader("🤖 AI 추천")
extra = st.text_input("AI에게 함께 알려줄 내용 (선택)",
                      placeholder="예: 금요일엔 회의가 많아요 / 미술관에 가고 싶어요")

if st.button("🔮 휴가 요일 추천 받기", type="primary"):
    # AI에게 줄 데이터 요약 (근거 자료)
    stats_lines = "\n".join(
        f"- {r['요일']}요일: 하루 평균 {r['평균 이용객']:,}명" for _, r in wk.iterrows())
    user_prompt = (
        f"내가 자주 이용하는 지하철역은 '{station}'역이야.\n\n"
        f"[2025년 요일별 하루 평균 이용객]\n{stats_lines}\n"
        + (f"\n[요일구분별 평균 혼잡도] {busy_summary}\n" if busy_summary else "")
        + (f"\n[추가 참고사항] {extra}\n" if extra else "")
        + "\n위 데이터를 근거로, 하루 휴가를 낸다면 어느 요일이 가장 좋을지 추천해줘. "
          "1) 추천 요일과 이유, 2) 피하면 좋은 요일, 3) 그날 지하철을 여유롭게 타는 꿀팁 "
          "순서로 짧고 친근하게 알려줘."
    )
    messages = [
        {"role": "system",
         "content": "너는 따뜻하고 친절한 데이터 분석 선생님이야. 반드시 순수 한국어로만 답해"},
        {"role": "user", "content": user_prompt},
    ]
    with st.chat_message("assistant"):
        solar_stream_answer(messages)   # 글자가 실시간으로 흘러나온다
else:
    st.caption("버튼을 누르면 위 분석 데이터를 바탕으로 AI가 휴가 요일을 추천해 드려요.")

st.divider()
st.caption("ⓒ 서울교통공사 역 분석 대시보드 · 예측 도우미 (2025년 통계 + Upstage Solar)")
