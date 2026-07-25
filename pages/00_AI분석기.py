# -*- coding: utf-8 -*-
"""
AI 분석 페이지 (pages/00_AI분석기.py)
- 위: 관심역 비교 분석 (최대 3곳 나란히 비교)
- 아래: AI 분석 도우미 채팅 (Upstage Solar, solar-open2)
"""
from core import *   # 공통 모듈 (데이터 로더, 스타일, Solar API 등)

page_setup("역 대 역 · AI 비교 분석실", "🥊")

st.markdown("## 🥊 역 대 역 — AI 비교 분석실")
try:
    st.page_link("main.py", label="⬅️ 메인 대시보드로 돌아가기")
except Exception:
    st.caption("⬅️ 메인 대시보드는 왼쪽 사이드바에서 열 수 있어요.")

keys = get_keys()
with st.spinner("역 목록 로딩 중..."):
    stations, _, _ = get_stations(keys)

# ═════════════════════════════════════════════
# 1) 관심역 비교 분석 (위쪽)
# ═════════════════════════════════════════════
st.markdown(
    """
    <div class="hero">
      <div class="hero-title">⚖️ 관심역 맞대결</div>
      <div class="hero-sub">최대 3개 역을 링 위에 올려 승하차·시간대 패턴·혼잡도를 겨뤄봅니다</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 관심역 선택 (최대 3곳)
default_fav = [s for s in ("강남", "잠실", "홍대입구") if s in stations][:3] or stations[:3]
fav = st.multiselect("관심역 선택 (최대 3곳)", stations, default=default_fav,
                     max_selections=3, key="fav_stations")

# 조회 기간 선택 (일별/월별/기간)
cmp_mode, cmp_dates, cmp_label = select_period("cmp")

if not fav:
    st.info("비교할 역을 1곳 이상 선택해 주세요.")
elif not cmp_dates:
    st.warning("조회 가능한 날짜가 없습니다. 다른 기간을 선택해 주세요.")
else:
    # 관심역별 승하차 데이터 수집
    cmp_tuple = tuple(d.strftime("%Y%m%d") for d in cmp_dates)
    fav_data = {}
    with st.spinner("관심역 데이터 로딩 중..."):
        for s_name in fav:
            df_s, e_s, _ = load_ridership_period(keys["riders"], cmp_tuple, s_name)
            fav_data[s_name] = df_s if e_s is None else pd.DataFrame()
    loaded = {k: v for k, v in fav_data.items() if v is not None and not v.empty}

    # KPI: 역별 총 이용객
    kpi_cols = st.columns(max(len(fav), 1))
    for i, s_name in enumerate(fav):
        df_s = fav_data.get(s_name)
        total = int(df_s["합계"].sum()) if df_s is not None and not df_s.empty else 0
        kpi_cols[i].metric(f"🚉 {s_name}", f"{total:,}명" if total else "데이터 없음",
                           help=f"조회 기간({cmp_label}) 총 이용객")

    if not loaded:
        st.warning("선택한 기간의 승하차 데이터를 불러오지 못했습니다.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("승하차 인원 비교")
            rows = []
            for s_name, df_s in loaded.items():
                rows.append({"역": s_name, "구분": "승차", "인원": int(df_s["승차"].sum())})
                rows.append({"역": s_name, "구분": "하차", "인원": int(df_s["하차"].sum())})
            comp = pd.DataFrame(rows)
            fig = px.bar(comp, x="역", y="인원", color="구분", barmode="group",
                         template=PLOTLY_TEMPLATE,
                         color_discrete_map={"승차": "#2F6BFF", "하차": "#0F172A"})
            fig.update_layout(height=380, margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.1))
            show_chart(fig)
        with c2:
            st.subheader("시간대별 이용 패턴 비교")
            hr_frames = []
            for s_name, df_s in loaded.items():
                if "시간" in df_s.columns and df_s["시간"].astype(bool).any():
                    g = df_s.groupby("시간", as_index=False)["합계"].sum()
                    g["역"] = s_name
                    hr_frames.append(g)
            if hr_frames:
                hdf = pd.concat(hr_frames).sort_values("시간")
                fig = px.line(hdf, x="시간", y="합계", color="역", markers=True,
                              template=PLOTLY_TEMPLATE,
                              labels={"합계": "이용객(명)", "시간": "시간대(시)"})
                fig.update_layout(height=380, margin=dict(t=20, b=10),
                                  legend=dict(orientation="h", y=1.1))
                show_chart(fig)
            else:
                st.info("시간대 데이터가 없습니다.")

        # 일별 추이 비교 (기간에 여러 날짜가 있을 때만)
        if any(df_s["날짜"].nunique() > 1 for df_s in loaded.values()):
            st.subheader("일별 이용 추이 비교")
            dd = []
            for s_name, df_s in loaded.items():
                g = df_s.groupby("날짜", as_index=False)["합계"].sum()
                g["역"] = s_name
                dd.append(g)
            ddf = pd.concat(dd)
            ddf["날짜"] = pd.to_datetime(ddf["날짜"], format="%Y%m%d", errors="coerce")
            fig = px.line(ddf.dropna(subset=["날짜"]), x="날짜", y="합계", color="역",
                          markers=True, template=PLOTLY_TEMPLATE,
                          labels={"합계": "이용객(명)"})
            fig.update_layout(height=400, margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.1))
            show_chart(fig)

    # 혼잡도 비교 (실시간 API)
    st.subheader("혼잡도 비교")
    busy_frames = []
    with st.spinner("혼잡도 데이터 로딩 중..."):
        for s_name in fav:
            bdf, berr = load_congestion(keys["busy"], s_name)
            if berr or bdf is None or bdf.empty:
                continue
            bsel = filter_by_station(bdf, s_name)
            if bsel.empty:
                continue
            tcols = detect_time_cols(bsel)
            if not tcols:
                continue
            bm = bsel.melt(value_vars=tcols, var_name="시간대", value_name="혼잡도")
            bm["혼잡도"] = to_num(bm["혼잡도"])
            bm["시간대"] = bm["시간대"].map(pretty_time_label)   # TIME0530 → 05:30
            g = (bm.dropna(subset=["혼잡도"])
                 .groupby("시간대", as_index=False)["혼잡도"].mean())
            g["역"] = s_name
            busy_frames.append((g, [pretty_time_label(c) for c in tcols]))
    if busy_frames:
        bfd = pd.concat([f[0] for f in busy_frames])
        order = busy_frames[0][1]
        fig = px.line(bfd, x="시간대", y="혼잡도", color="역", markers=True,
                      template=PLOTLY_TEMPLATE,
                      category_orders={"시간대": order})
        fig.update_xaxes(tickangle=-45, tickfont=dict(size=10), nticks=13)
        fig.add_hline(y=100, line_dash="dash", line_color="red",
                      annotation_text="혼잡 기준(100%)")
        fig.update_layout(height=420, margin=dict(t=20, b=10),
                          legend=dict(orientation="h", y=1.12))
        show_chart(fig)
        st.caption("역별 시간대 평균 혼잡도 · 출처: 서울교통공사 1~8호선 30분 단위 평균 "
                   "(좌석 수만큼 승차 시 34%, 100% = 정원 기준 만차)")
    else:
        st.info("혼잡도 데이터를 불러오지 못했습니다. (BUSY_API_KEY 설정 또는 데이터 제공 여부를 확인하세요)")

st.divider()

# ═════════════════════════════════════════════
# 2) AI 분석 도우미 채팅 (아래쪽)
# ═════════════════════════════════════════════
st.subheader("💬 AI 분석 도우미")
st.caption("역 데이터에 대해 궁금한 점을 물어보세요. 이전 대화를 기억하며 이어서 답해요. (Upstage Solar)")

# 대화 기록을 세션에 저장 → 새로고침 전까지 기억
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# 대화를 처음부터 다시 시작하고 싶을 때
if st.session_state.chat_messages and st.button("🗑️ 대화 지우기"):
    st.session_state.chat_messages = []
    st.rerun()

# 지금까지의 대화를 말풍선으로 표시
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 채팅 입력창
user_input = st.chat_input("예: 강남역과 잠실역 중 어디가 더 붐비나요?")

if user_input:
    # 사용자의 말을 기록하고 말풍선으로 표시
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # AI 성격(시스템 프롬프트) + 현재 화면 정보(참고용)
    system_prompt = "너는 따뜻하고 친절한 데이터 분석 선생님이야. 반드시 순수 한국어로만 답해"
    context = f"[참고 정보] 사용자가 비교 중인 관심역: {', '.join(fav) if fav else '없음'}"
    if fav and cmp_label:
        context += f", 조회 기간: {cmp_label}"
    messages = ([{"role": "system", "content": system_prompt},
                 {"role": "system", "content": context}]
                + st.session_state.chat_messages)

    # Solar 호출: 답이 글자 단위로 실시간 출력됨
    with st.chat_message("assistant"):
        answer = solar_stream_answer(messages)

    # AI의 답도 기록 → 다음 질문에서 문맥 기억
    if answer:
        st.session_state.chat_messages.append({"role": "assistant", "content": answer})

st.divider()
st.caption("ⓒ 서울교통공사 역 분석 대시보드 · AI 분석 (관심역 비교 + Solar 도우미)")
