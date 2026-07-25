# -*- coding: utf-8 -*-
"""
서울교통공사 역 분석 대시보드 (main.py)
- 이 파일: 역 종합 현황 / 혼잡도 / 주변 역 지도
- pages/00_AI분석기.py: 관심역 비교 분석 + AI 도우미
- pages/01_예측도우미.py: 휴가 요일 추천 AI
- 공통 로더·유틸·스타일은 core.py에 있습니다
- 실행: streamlit run main.py
"""
from core import *   # 공통 모듈 (데이터 로더, 스타일, Solar API 등)

page_setup()         # 페이지 설정 + 공통 CSS

# ─────────────────────────────────────────────
# 상단 컨트롤 (역 검색 → 조회 방식) : 좌우 구분 없이 한 화면
# ─────────────────────────────────────────────
keys = get_keys()          # 모든 API 키 (core.py에서 로드)

# 조회 가능 날짜 범위 (2025년 CSV 시작일 ~ 어제)
MIN_DAY, MAX_DAY, API_MIN = date_bounds()

st.markdown("## 🚇 지하철 인사이트 랩 — 우리 역, 얼마나 붐빌까?")

# ── 페이지 선택: 역 종합 현황 / 관심역 비교 분석 ──
page = st.radio("페이지",
                ["📊 역 종합 현황", "📈 혼잡도", "🗺️ 주변 역 지도"],
                horizontal=True, label_visibility="collapsed")

# 별도 페이지로 분리된 기능 바로가기
# (배포 환경에서 페이지를 못 찾아도 앱이 죽지 않게 예외 처리)
def safe_page_link(path, label):
    try:
        st.page_link(path, label=label)
    except Exception:
        st.caption(f"{label} → 왼쪽 사이드바(＞ 버튼)에서 열 수 있어요.")

nav1, nav2, _nav = st.columns([1.2, 1, 1.8])
with nav1:
    safe_page_link("pages/00_AI분석기.py", "🥊 역 대 역 — AI 비교 분석실")
with nav2:
    safe_page_link("pages/01_예측도우미.py", "🏖️ 휴가 타이밍 예측기")

# 역 목록 확보 (API 스냅샷 → 실패 시 첨부 CSV)
with st.spinner("역 목록 로딩 중..."):
    stations, rid_df, rid_err = get_stations(keys)




# ═════════════════════════════════════════════
# 페이지 1: 역 종합 현황
# ═════════════════════════════════════════════
# ── 1) 역 검색 (최상단) ──
col_search, col_select = st.columns([1, 1.6])
if stations:
    search = col_search.text_input("🔍 역 검색", placeholder="예: 강남, 시청, 왕십리")
    filtered = ([s for s in stations if norm_station(search) in norm_station(s)]
                if search else stations)
    if not filtered:
        col_search.warning("검색 결과가 없어 전체 목록을 표시합니다.")
        filtered = stations
    default_idx = filtered.index("강남") if "강남" in filtered else 0
    station = col_select.selectbox("역 선택", filtered, index=default_idx)
else:
    station = col_search.text_input("🔍 역명 직접 입력", value="강남")
    if rid_err:
        st.error(f"승하차 API: {rid_err}")

# ═══ 페이지: 혼잡도 (탭 없이 바로 표시) ═══
if page == "📈 혼잡도":
    # 데이터 출처·산정 기준 안내
    with st.expander("ℹ️ 혼잡도 데이터 안내 (출처: 서울교통공사)", expanded=False):
        st.markdown(
            """
            - **출처**: 서울교통공사 지하철 혼잡도 정보 (2024년부터 **분기별** 제공)
            - **의미**: 1~8호선 **30분 단위 평균 혼잡도** — 30분간 지나는 열차들의 평균값 (단위: %)
            - **산정 기준**: 정원 대비 승차 인원 비율. 승차 인원이 **좌석 수와 같으면 혼잡도 34%**
            - **데이터 구성**: 요일구분(평일·토요일·일요일) · 호선 · 역번호 · 역명 · 상하선 구분 · 30분 단위 혼잡도
            """
        )
    with st.spinner("혼잡도 데이터 로딩 중..."):
        busy_df, busy_err = load_congestion(keys["busy"], station)
    if busy_err:
        st.warning(f"혼잡도 API: {busy_err}")
    elif busy_df.empty:
        st.info("혼잡도 데이터가 없습니다.")
    else:
        busy_sel = filter_by_station(busy_df, station)
        target = busy_sel if not busy_sel.empty else busy_df
        if busy_sel.empty:
            st.info("선택한 역의 혼잡도 행을 찾지 못해 조회된 전체 데이터를 표시합니다.")
        time_cols = detect_time_cols(target)
        if time_cols:
            st.subheader("시간대별 혼잡도")
            # 요일(DOW_SE)·상하행(UP_DOWN_SE)을 합쳐 선(line) 구분 라벨로 사용
            target = target.copy()
            label_parts = [c for c in target.columns
                           if find_col([c], ["DOW", "요일", "UP_DOWN", "UPDN", "방향", "DRCT"])]
            if label_parts:
                target["구분"] = target[label_parts].astype(str).agg(" · ".join, axis=1)
                label_col = "구분"
            else:
                label_col = None
            m = target.melt(id_vars=[label_col] if label_col else None,
                            value_vars=time_cols, var_name="시간대", value_name="혼잡도")
            m["혼잡도"] = to_num(m["혼잡도"])
            m = m.dropna(subset=["혼잡도"])
            m["시간대"] = m["시간대"].map(pretty_time_label)   # TIME0530 → 05:30
            order = [pretty_time_label(c) for c in time_cols]
            fig = px.line(m, x="시간대", y="혼잡도",
                          color=label_col if label_col else None,
                          markers=True, template=PLOTLY_TEMPLATE,
                          category_orders={"시간대": order})
            # 시간대 눈금이 38개라 모바일에서 겹치지 않게 기울이고 개수 제한
            fig.update_xaxes(tickangle=-45, tickfont=dict(size=10), nticks=13)
            fig.add_hline(y=100, line_dash="dash", line_color="red",
                          annotation_text="혼잡 기준(100%)")
            fig.update_layout(height=420, margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.12))
            show_chart(fig)
        st.subheader("원본 데이터")
        st.dataframe(target.head(300), use_container_width=True, hide_index=True)
    st.stop()   # 이 페이지는 여기서 끝


# ═══ 페이지: 주변 역 지도 + 혼잡도 비교 ═══
if page == "🗺️ 주변 역 지도":
    with st.spinner("역 좌표 데이터 로딩 중..."):
        master, m_err = load_station_master(keys["map"])
    if m_err:
        st.warning(f"역사 마스터 API: {m_err}")
        st.caption("Secrets에 MAP_API_KEY(서울열린데이터광장 인증키)를 등록해 주세요.")
    elif master.empty:
        st.info("역 좌표 데이터가 없습니다.")
    else:
        sel_rows = master[master["역명"].apply(lambda x: station_match(x, station))]
        if sel_rows.empty:
            st.info(f"'{station}' 역의 좌표를 찾지 못했습니다.")
        else:
            # 선택 역의 대표 좌표 (환승역은 호선별 좌표의 평균)
            lat0, lon0 = float(sel_rows["위도"].mean()), float(sel_rows["경도"].mean())
            radius = st.slider("주변 역 탐색 반경 (km)", 0.5, 3.0, 1.5, 0.5)

            # 모든 역까지의 거리 계산 → 반경 안의 역만 추리기
            near = master.copy()
            near["거리(km)"] = near.apply(
                lambda r: haversine_km(lat0, lon0, r["위도"], r["경도"]), axis=1)
            near = near[near["거리(km)"] <= radius].sort_values("거리(km)")

            # ── 지도: 호선별 색상 마커 + 역명 라벨 ──
            st.subheader(f"🗺️ {station} 주변 {radius}km 역 지도")
            fig = px.scatter_mapbox(
                near, lat="위도", lon="경도", color="호선", text="역명",
                hover_name="역명",
                hover_data={"호선": True, "거리(km)": ":.2f", "위도": False, "경도": False},
                color_discrete_map=LINE_COLORS, zoom=13.3, height=520)
            fig.update_traces(marker=dict(size=13), textposition="top center",
                              textfont=dict(size=11, color="#0F172A"))
            # 선택한 역은 큰 별도 마커로 강조
            fig.add_trace(go.Scattermapbox(
                lat=[lat0], lon=[lon0], mode="markers",
                marker=dict(size=22, color="#0F172A"), name=f"⭐ {station}"))
            fig.update_layout(mapbox_style="open-street-map",
                              margin=dict(t=0, b=0, l=0, r=0),
                              legend=dict(orientation="h", y=-0.04))
            show_chart(fig)

            # ── 주변 역 목록 (호선 묶음 + 거리) ──
            info = (near.groupby("역명")
                    .agg(호선=("호선", lambda s: ", ".join(sorted(set(s)))),
                         거리km=("거리(km)", "min"))
                    .reset_index().sort_values("거리km"))
            info["거리km"] = info["거리km"].round(2)
            st.dataframe(info, use_container_width=True, hide_index=True)

            # ── 주변 역 혼잡도 한눈에 비교 (히트맵) ──
            st.subheader("🔥 주변 역 혼잡도 비교")
            near_names = info["역명"].head(6).tolist()   # 가까운 순 최대 6곳
            heat_rows, time_order = [], None
            with st.spinner("주변 역 혼잡도 수집 중..."):
                for nm in near_names:
                    bdf, berr = load_congestion(keys["busy"], nm)
                    if berr or bdf is None or bdf.empty:
                        continue
                    bsel = filter_by_station(bdf, nm)
                    if bsel.empty:
                        continue
                    tcols = detect_time_cols(bsel)
                    if not tcols:
                        continue
                    # 요일·상하행을 평균 내서 역별 시간대 혼잡도 한 줄로
                    vals = bsel[tcols].apply(to_num).mean()
                    labels = [pretty_time_label(c) for c in tcols]
                    heat_rows.append(pd.Series(vals.values, index=labels, name=nm))
                    time_order = labels
            if heat_rows:
                hm = pd.DataFrame(heat_rows)
                hm = hm[[c for c in time_order if c in hm.columns]]
                fig = px.imshow(hm, aspect="auto", color_continuous_scale="YlOrRd",
                                labels=dict(x="시간대", y="역", color="혼잡도(%)"))
                fig.update_xaxes(tickangle=-45, tickfont=dict(size=9))
                fig.update_layout(height=120 + 46 * len(hm), margin=dict(t=20, b=10))
                show_chart(fig)
                st.caption("색이 진할수록 혼잡 (요일·상하행 평균) · 출처: 서울교통공사 1~8호선 "
                           "30분 단위 평균 혼잡도 (좌석 수만큼 승차 시 34%, 100% = 정원 기준 만차)")
            else:
                st.info("주변 역의 혼잡도 데이터를 불러오지 못했습니다. (BUSY_API_KEY 필요)")
    st.stop()   # 이 페이지는 여기서 끝


# ── 2) 조회 기간: 일별 / 최근 일주일 누적 (실시간 API 제공 범위에 맞춤) ──
mode = st.radio("조회 기간", ["일별", "최근 일주일 누적"],
                horizontal=True, key="main_mode")
if mode == "일별":
    d = st.date_input("날짜", value=MAX_DAY,
                      min_value=API_MIN, max_value=MAX_DAY, key="main_day")
    date_list = [d]
    period_label = d.strftime("%Y-%m-%d")
else:
    # 최근 일주일(7일 전 ~ 어제)을 모두 합산해서 보여준다
    date_list = [API_MIN + dt.timedelta(days=i)
                 for i in range((MAX_DAY - API_MIN).days + 1)]
    period_label = f"최근 일주일 ({API_MIN.strftime('%m.%d')} ~ {MAX_DAY.strftime('%m.%d')})"
st.caption("ℹ️ 승하차 통계는 최근 일주일 데이터가 제공됩니다.")

# 추이 그래프 등에서 쓰는 기준일 = 조회 기간의 마지막 날
base_date = date_list[-1] if date_list else MAX_DAY

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
# ── 상단 히어로 배너 (선택한 역 이름 + 조회 기간) ──
st.markdown(
    f"""
    <div class="hero">
      <div class="hero-title">🚇 {station} <span>역 종합 현황</span></div>
      <div class="hero-sub">조회 기간 {period_label} ({mode}) ·
      서울열린데이터광장 / 공공데이터포털 데이터</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 선택한 기간의 날짜들을 문자열(YYYYMMDD) 묶음으로 변환해 조회
ds_tuple = tuple(d.strftime("%Y%m%d") for d in date_list)
with st.spinner("선택 역 승하차 데이터 로딩 중..."):
    sel, sel_err, sel_note = load_ridership_period(keys["riders"], ds_tuple, station)
if sel_note:
    st.info(sel_note)

trans_df, trans_err = load_transfer(keys["transfer"])
trans_sel = filter_by_station(trans_df, station)
trans_total = None
if not trans_sel.empty:
    nc = numeric_cols(trans_sel)
    if nc:
        trans_total = int(to_num(trans_sel[nc].stack()).sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("승차 인원", f"{int(sel['승차'].sum()):,}명" if not sel.empty else "―")
k2.metric("하차 인원", f"{int(sel['하차'].sum()):,}명" if not sel.empty else "―")
k3.metric("총 이용객", f"{int(sel['합계'].sum()):,}명" if not sel.empty else "―")
k4.metric("환승 인원(일)", f"{trans_total:,}명" if trans_total else "데이터 없음")

st.divider()

tab_ride, tab_trans, tab_bld, tab_elev = st.tabs(
    ["🚏 승하차 분석", "🔄 환승 인원", "🏗️ 역사 건축 현황", "♿ 승강기·교통약자 시설"]
)

# ── 탭1: 승하차 ──
with tab_ride:
    if sel_err:
        st.warning(f"승하차 API: {sel_err}")
    elif sel.empty:
        st.info("선택한 역의 승하차 데이터가 없습니다. 다른 날짜를 선택해 보세요.")
    else:
        # 시간대별 승하차 (pasngHr 기준)
        if "시간" in sel.columns and sel["시간"].astype(bool).any():
            st.subheader("시간대별 승하차")
            hourly = (sel.groupby("시간", as_index=False)[["승차", "하차"]].sum()
                      .sort_values("시간"))
            fig = go.Figure()
            fig.add_trace(go.Bar(x=hourly["시간"], y=hourly["승차"], name="승차",
                                 marker_color="#2F6BFF"))
            fig.add_trace(go.Bar(x=hourly["시간"], y=hourly["하차"], name="하차",
                                 marker_color="#93C5FD"))
            fig.update_layout(template=PLOTLY_TEMPLATE, barmode="group", height=380,
                              xaxis_title="시간대(시)", yaxis_title="인원(명)",
                              margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.1))
            show_chart(fig)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("호선별 승하차 (선택 역)")
            m = (sel.groupby("호선", as_index=False)[["승차", "하차"]].sum()
                 .melt(id_vars=["호선"], value_vars=["승차", "하차"],
                       var_name="구분", value_name="인원"))
            fig = px.bar(m, x="호선", y="인원", color="구분", barmode="group",
                         template=PLOTLY_TEMPLATE,
                         color_discrete_map={"승차": "#2F6BFF", "하차": "#93C5FD"})
            fig.update_layout(height=360, margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.1))
            show_chart(fig)
        with c2:
            # 기간/월별 조회면 이미 받아온 데이터로 일별 추이를 그리고,
            # 일별 조회면 최근 7일 추이를 따로 수집해서 보여준다
            if "날짜" in sel.columns and sel["날짜"].nunique() > 1:
                st.subheader("일별 이용 추이 (조회 기간)")
                g = (sel.groupby("날짜")[["승차", "하차"]].sum()
                     .reset_index().sort_values("날짜"))
                g["날짜"] = pd.to_datetime(g["날짜"], format="%Y%m%d", errors="coerce")
                trend = g.dropna(subset=["날짜"])
            else:
                st.subheader(f"최근 {TREND_DAYS}일 이용 추이")
                with st.spinner("추이 데이터 수집 중..."):
                    trend = load_trend(keys["riders"], base_date, station)
            if trend.empty:
                st.info("추이 데이터를 불러올 수 없습니다.")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=trend["날짜"], y=trend["승차"], name="승차",
                                         mode="lines+markers",
                                         line=dict(color="#2F6BFF", width=3)))
                fig.add_trace(go.Scatter(x=trend["날짜"], y=trend["하차"], name="하차",
                                         mode="lines+markers",
                                         line=dict(color="#93C5FD", width=3)))
                fig.update_layout(template=PLOTLY_TEMPLATE, height=360,
                                  margin=dict(t=20, b=10),
                                  legend=dict(orientation="h", y=1.1))
                show_chart(fig)

    if not rid_df.empty:
        snapshot_hr = (rid_df["시간"].iloc[0]
                       if "시간" in rid_df.columns and rid_df["시간"].astype(bool).any()
                       else "")
        title = "전체 역 이용객 순위 (Top 20)"
        if snapshot_hr and rid_df["시간"].nunique() == 1:
            title += f" · {snapshot_hr}시 시간대 기준"
        st.subheader(title)
        top = (rid_df.groupby("역명", as_index=False)["합계"].sum()
               .sort_values("합계", ascending=False).head(20))
        top["선택"] = top["역명"].apply(
            lambda x: "선택 역" if station_match(x, station) else "기타")
        fig = px.bar(top, x="합계", y="역명", orientation="h", color="선택",
                     template=PLOTLY_TEMPLATE,
                     labels={"합계": "총 이용객(명)"},
                     color_discrete_map={"선택 역": "#2F6BFF", "기타": "#D8E0EA"})
        fig.update_layout(height=560, yaxis=dict(autorange="reversed"),
                          margin=dict(t=20, b=10), showlegend=False)
        show_chart(fig)
    elif rid_err:
        st.warning(f"역 목록/순위 조회 실패: {rid_err}")

# ── 탭2: 환승 ──
with tab_trans:
    if trans_err:
        st.warning(f"환승 API: {trans_err}")
    elif trans_df.empty:
        st.info("환승 인원 데이터가 없습니다.")
    else:
        if trans_sel.empty:
            st.info(f"'{station}'은(는) 환승 인원 데이터에 없습니다. (환승역이 아닐 수 있습니다)")
        else:
            st.subheader("선택 역 환승 인원")
            nc = numeric_cols(trans_sel)
            if nc:
                melted = trans_sel.melt(value_vars=nc, var_name="항목", value_name="인원")
                melted["인원"] = to_num(melted["인원"])
                agg = melted.groupby("항목", as_index=False)["인원"].sum()
                fig = px.bar(agg, x="항목", y="인원", color="항목",
                             template=PLOTLY_TEMPLATE,
                             color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(height=380, margin=dict(t=20, b=10), showlegend=False)
                show_chart(fig)
            st.dataframe(trans_sel, use_container_width=True, hide_index=True)

        c_stn = find_col(trans_df.columns, STATION_COL_KWS)
        nc_all = numeric_cols(trans_df)
        if c_stn and nc_all:
            st.subheader("환승 인원 상위 15개 역")
            tmp = trans_df.copy()
            tmp["_합계"] = sum(to_num(tmp[c]).fillna(0) for c in nc_all)
            rank = (tmp.groupby(c_stn, as_index=False)["_합계"].sum()
                    .sort_values("_합계", ascending=False).head(15))
            rank["선택"] = rank[c_stn].apply(
                lambda x: "선택 역" if station_match(x, station) else "기타")
            fig = px.bar(rank, x="_합계", y=c_stn, orientation="h", color="선택",
                         template=PLOTLY_TEMPLATE,
                         labels={"_합계": "환승 인원(명)", c_stn: "역명"},
                         color_discrete_map={"선택 역": "#2F6BFF", "기타": "#D8E0EA"})
            fig.update_layout(height=480, yaxis=dict(autorange="reversed"),
                              margin=dict(t=20, b=10), showlegend=False)
            show_chart(fig)

# ── 탭4: 역사 건축 현황 ──
with tab_bld:
    with st.spinner("건축 현황 데이터 로딩 중..."):
        bld_df, bld_err = load_building(keys["building"])
    if bld_err:
        st.warning(f"건축 현황 API: {bld_err}")
    elif bld_df.empty:
        st.info("역사 건축 현황 데이터가 없습니다.")
    else:
        bld_sel = filter_by_station(bld_df, station)
        if bld_sel.empty:
            st.info(f"'{station}' 역의 건축 현황을 찾지 못했습니다. 아래에서 직접 검색해 보세요.")
            q = st.text_input("건축 현황 내 검색", key="bld_search")
            view = bld_df
            if q:
                mask = (bld_df.astype(str)
                        .apply(lambda r: r.str.contains(q, na=False)).any(axis=1))
                view = bld_df[mask]
            st.dataframe(view.head(200), use_container_width=True, hide_index=True)
        else:
            st.subheader("선택 역 건축 정보")
            row = bld_sel.iloc[0]
            info_cols = st.columns(3)
            shown = 0
            for col_name, val in row.items():
                if pd.isna(val) or str(val).strip() == "":
                    continue
                info_cols[shown % 3].markdown(f"**{col_name}**  \n{val}")
                shown += 1
            if len(bld_sel) > 1:
                st.dataframe(bld_sel, use_container_width=True, hide_index=True)

# ── 탭5: 승강기 ──
with tab_elev:
    with st.spinner("승강기 데이터 로딩 중..."):
        elev_df, elev_err = load_elevator(keys["elevator"], station)
    if elev_err:
        st.warning(f"승강기 API: {elev_err}")
    elif elev_df.empty:
        st.info("승강기·교통약자 시설 데이터가 없습니다.")
    else:
        elev_sel = filter_by_station(elev_df, station)
        if elev_sel.empty:
            st.info(f"'{station}' 역의 승강기 데이터를 찾지 못했습니다.")
        else:
            c_kind = find_col(elev_sel.columns, ["ELVTR_SE", "KIND", "구분", "종류", "TYPE"])
            c_use = find_col(elev_sel.columns, ["USE_YN", "사용", "가동", "STTS", "STATUS"])
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("시설 종류별 현황")
                if c_kind:
                    cnt = elev_sel[c_kind].value_counts().reset_index()
                    cnt.columns = ["종류", "대수"]
                    fig = px.pie(cnt, names="종류", values="대수", hole=0.45,
                                 template=PLOTLY_TEMPLATE,
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_layout(height=340, margin=dict(t=20, b=10))
                    show_chart(fig)
                else:
                    st.metric("총 시설 수", f"{len(elev_sel)}대")
            with c2:
                st.subheader("가동/사용 상태")
                if c_use:
                    cnt = elev_sel[c_use].value_counts().reset_index()
                    cnt.columns = ["상태", "대수"]
                    fig = px.bar(cnt, x="상태", y="대수", color="상태",
                                 template=PLOTLY_TEMPLATE,
                                 color_discrete_sequence=["#00A84D", "#2F6BFF", "#D8E0EA"])
                    fig.update_layout(height=340, margin=dict(t=20, b=10),
                                      showlegend=False)
                    show_chart(fig)
                else:
                    st.info("상태 컬럼을 인식하지 못했습니다. 아래 표를 확인하세요.")
            st.subheader("시설 목록")
            st.dataframe(elev_sel, use_container_width=True, hide_index=True)

st.divider()
st.caption("ⓒ 서울교통공사 역 분석 대시보드 · 데이터: 서울열린데이터광장, 공공데이터포털 · AI: Upstage Solar · API 키는 Secrets로 안전하게 관리됩니다.")
