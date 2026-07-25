# -*- coding: utf-8 -*-
"""
서울교통공사 역 분석 대시보드
- 승하차인원 / 환승인원 / 혼잡도 / 역사 건축 현황 / 승강기(교통약자 시설)
- 모든 API Key는 st.secrets에서 로드 (하드코딩 금지)
"""
import re
import datetime as dt
import xml.etree.ElementTree as ET
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────────
# 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="서울교통공사 역 분석 대시보드",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        background: rgba(28, 131, 225, 0.06);
        border: 1px solid rgba(28, 131, 225, 0.15);
        border-radius: 12px; padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] {font-size: 0.85rem;}
    @media (max-width: 640px) {
        [data-testid="stMetricValue"] {font-size: 1.3rem;}
        .block-container {padding-left: 0.8rem; padding-right: 0.8rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SEOUL_BASE = "http://openapi.seoul.go.kr:8088"
ODCLOUD_DOCS = "https://infuser.odcloud.kr/oas/docs?namespace=15044258/v1"
ODCLOUD_API = "https://api.odcloud.kr/api"
TIMEOUT = 12
TREND_DAYS = 14

PLOTLY_TEMPLATE = "plotly_white"


# ─────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────
def get_secret(name: str):
    """Secrets에서 키를 안전하게 로드. 키 값은 절대 화면/로그에 출력하지 않는다."""
    try:
        v = st.secrets.get(name)
        # 공백/따옴표가 섞여 들어간 경우 정리
        v = str(v).strip().strip('"').strip("'").strip() if v else ""
        return v or None
    except Exception:
        return None


def norm_station(name: str) -> str:
    if not name:
        return ""
    n = re.sub(r"\(.*?\)", "", str(name))
    return n.replace(" ", "").strip()


def station_match(a: str, b: str) -> bool:
    a, b = norm_station(a), norm_station(b)
    if not a or not b:
        return False
    return a == b or a == b + "역" or b == a + "역"


def find_col(cols, keywords):
    cols = list(cols)
    for kw in keywords:
        for c in cols:
            if kw.lower() in str(c).lower():
                return c
    return None


def to_num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(",", ""), errors="coerce")


def numeric_cols(df: pd.DataFrame):
    """전부 숫자(콤마 허용)로 이루어진 컬럼 목록."""
    out = []
    for c in df.columns:
        s = df[c].astype(str).str.replace(",", "").str.strip()
        if len(s) and s.str.match(r"^-?\d+\.?\d*$").all():
            out.append(c)
    return out


def _parse_xml_error(content: bytes) -> str:
    """서울 API가 반환한 XML/HTML 에러 문서에서 원인 메시지를 추출."""
    try:
        root = ET.fromstring(content)
        code_el = root.find(".//CODE")
        msg_el = root.find(".//MESSAGE")
        code = code_el.text.strip() if code_el is not None and code_el.text else ""
        msg = msg_el.text.strip() if msg_el is not None and msg_el.text else ""
        if code or msg:
            hint = ""
            if "인증키" in msg or code in ("INFO-100", "ERROR-500"):
                hint = " → Secrets에 등록한 인증키를 확인하세요. (서울열린데이터광장에서 발급한 키인지, 공백/오타가 없는지)"
            return f"API 오류 [{code}]: {msg}{hint}"
    except ET.ParseError:
        pass
    return "응답 파싱 실패: 서버가 예상하지 못한 형식을 반환했습니다. 인증키가 유효한지 확인하세요."


# ─────────────────────────────────────────────
# 공통 API 호출 (서울열린데이터광장)
# ─────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_seoul(api_key: str, service: str, fmt: str = "json",
                start: int = 1, end: int = 1000, extra: tuple = ()):
    """반환: (rows(list[dict]) | None, error_message | None). 키는 에러 메시지에 포함하지 않음."""
    if not api_key:
        return None, "API 키가 Secrets에 설정되지 않았습니다."
    parts = [SEOUL_BASE, api_key, fmt, service, str(start), str(end)]
    parts += [quote(str(e)) for e in extra if str(e)]
    url = "/".join(parts)
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        return None, "API 호출 실패 (네트워크 또는 서버 오류)"

    if fmt == "json":
        try:
            data = r.json()
        except ValueError:
            # 인증키가 유효하지 않으면 JSON 요청에도 XML 에러 문서가 반환됨
            return None, _parse_xml_error(r.content)
        if service in data:
            block = data[service]
            code = (block.get("RESULT") or {}).get("CODE", "")
            if str(code).startswith("INFO-200"):
                return [], None
            return block.get("row") or [], None
        code = str((data.get("RESULT") or {}).get("CODE", ""))
        msg = (data.get("RESULT") or {}).get("MESSAGE", "알 수 없는 오류")
        if code.startswith("INFO-200"):
            return [], None
        return None, f"API 오류: {msg}"

    # XML
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return None, "응답 파싱 실패 (XML 형식 오류)"
    code_el = root.find(".//CODE")
    code = code_el.text.strip() if code_el is not None and code_el.text else ""
    rows = [{child.tag: (child.text or "").strip() for child in row}
            for row in root.iter("row")]
    if not rows:
        if code.startswith("INFO-200"):
            return [], None
        if code and not code.startswith("INFO-000"):
            msg_el = root.find(".//MESSAGE")
            msg = msg_el.text.strip() if msg_el is not None and msg_el.text else "알 수 없는 오류"
            return None, f"API 오류: {msg}"
    return rows, None


def fetch_seoul_with_fallback(api_key, service, fmt, station=None):
    """역명 파라미터를 지원하면 필터 요청, 실패 시 전체 조회 후 클라이언트 필터링."""
    if station:
        rows, err = fetch_seoul(api_key, service, fmt, 1, 1000, (station,))
        if rows:
            return rows, None
    return fetch_seoul(api_key, service, fmt, 1, 1000)


# ─────────────────────────────────────────────
# 1) 역별 승하차인원 (공공데이터포털 B553766/psgr/getStnPsgr)
# ─────────────────────────────────────────────
RIDERS_ENDPOINT = "https://apis.data.go.kr/B553766/psgr/getStnPsgr"


def _deep_get(obj, key):
    """중첩 dict/list에서 key 값을 재귀 탐색."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() == key.lower():
                return v
            r = _deep_get(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for it in obj:
            r = _deep_get(it, key)
            if r is not None:
                return r
    return None


def _find_records(obj):
    """응답 구조가 어떻든 dict 리스트(레코드 목록)를 재귀 탐색."""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            return obj
        for it in obj:
            r = _find_records(it)
            if r:
                return r
    elif isinstance(obj, dict):
        for k in ("item", "items", "data", "row", "list"):
            if k in obj:
                r = _find_records(obj[k])
                if r:
                    return r
        for v in obj.values():
            r = _find_records(v)
            if r:
                return r
    return None


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_riders_page(api_key: str, page: int, num_rows: int, date_str: str = ""):
    """반환: (rows|None, err|None, total_count)"""
    if not api_key:
        return None, "API 키가 Secrets에 설정되지 않았습니다.", 0
    params = {"serviceKey": api_key, "pageNo": page,
              "numOfRows": num_rows, "dataType": "JSON"}
    if date_str:
        params["dt"] = date_str
    try:
        r = requests.get(RIDERS_ENDPOINT, params=params, timeout=TIMEOUT)
    except requests.RequestException:
        return None, "API 호출 실패 (네트워크 또는 서버 오류)", 0

    # JSON 시도
    try:
        data = r.json()
        code = str(_deep_get(data, "resultCode") or "")
        if code and code not in ("00", "0", "INFO-000", "NORMAL_SERVICE"):
            msg = _deep_get(data, "resultMsg") or ""
            return None, f"API 오류 [{code}]: {msg}", 0
        rows = _find_records(data) or []
        try:
            total = int(_deep_get(data, "totalCount") or len(rows))
        except (TypeError, ValueError):
            total = len(rows)
        return rows, None, total
    except ValueError:
        pass

    # XML 시도 (게이트웨이 인증 오류 포함)
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return None, "응답 파싱 실패: 인증키(Decoding 키 사용 여부)를 확인하세요.", 0
    auth = root.find(".//returnAuthMsg")
    if auth is not None and auth.text:
        return None, (f"인증 오류: {auth.text.strip()} → 공공데이터포털 인증키가 맞는지, "
                      "활용신청이 승인되었는지 확인하세요."), 0
    rc = root.find(".//resultCode")
    if rc is not None and rc.text and rc.text.strip() not in ("00", "0"):
        rm = root.find(".//resultMsg")
        msg = rm.text.strip() if rm is not None and rm.text else ""
        return None, f"API 오류 [{rc.text.strip()}]: {msg}", 0
    items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
    if not items:
        items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("row")]
    tc = root.find(".//totalCount")
    total = int(tc.text) if tc is not None and tc.text and tc.text.strip().isdigit() else len(items)
    return items, None, total


def _standardize_riders(df: pd.DataFrame):
    """API 응답 컬럼명을 표준(날짜/호선/역명/승차/하차/합계)으로 변환."""
    cols = list(df.columns)
    c_date = find_col(cols, ["useYmd", "use_ymd", "sttusYmd", "ymd", "opDate", "일자", "date"])
    if not c_date:
        c_date = find_col([c for c in cols if "reg" not in str(c).lower()], ["dt"])
    c_stn = (find_col(cols, ["stnNm", "staNm", "stationNm", "역명", "stns_nm", "sub_sta_nm"])
             or find_col(cols, ["stn", "sta"]))
    c_line = find_col(cols, ["lineNm", "line", "호선", "rout"])
    c_ride = find_col(cols, ["ride", "gton", "승차"])
    c_alight = find_col(cols, ["algh", "alight", "gtoff", "하차"])
    if not c_stn:
        return pd.DataFrame(), "역명 컬럼 인식 실패. 응답 컬럼: " + ", ".join(map(str, cols))
    if not (c_ride and c_alight):
        # 이름으로 못 찾으면: 코드/날짜성 컬럼을 제외한 숫자 컬럼 2개를 승차/하차로 간주
        nums = []
        for c in numeric_cols(df):
            name = str(c).lower()
            if c in (c_date,) or "cd" in name or "no" in name:
                continue
            v = to_num(df[c])
            if v.max() is not None and pd.notna(v.max()) and v.max() > 5_000_000:
                continue  # 날짜(YYYYMMDD) 등 제외
            nums.append(c)
        if len(nums) >= 2:
            c_ride, c_alight = nums[0], nums[1]
        else:
            return pd.DataFrame(), "승하차 인원 컬럼 인식 실패. 응답 컬럼: " + ", ".join(map(str, cols))
    out = pd.DataFrame({
        "날짜": (df[c_date].astype(str).str.replace("-", "").str[:8] if c_date else ""),
        "호선": (df[c_line].astype(str) if c_line else "전체"),
        "역명": df[c_stn].astype(str),
        "승차": to_num(df[c_ride]).fillna(0).astype(int),
        "하차": to_num(df[c_alight]).fillna(0).astype(int),
    })
    out["합계"] = out["승차"] + out["하차"]
    return out, None


@st.cache_data(ttl=1800, show_spinner=False)
def load_riders_raw(api_key: str, date_str: str = "", max_pages: int = 3):
    """페이지네이션 포함 원본 수집 → 표준 DataFrame. 반환 (df, err)."""
    all_rows = []
    for page in range(1, max_pages + 1):
        rows, err, total = _fetch_riders_page(api_key, page, 1000, date_str)
        if err:
            if page == 1:
                return pd.DataFrame(), err
            break
        if not rows:
            break
        all_rows.extend(rows)
        if len(all_rows) >= total:
            break
    if not all_rows:
        return pd.DataFrame(), None
    return _standardize_riders(pd.DataFrame(all_rows))


def load_ridership(api_key: str, date_str: str):
    """선택 날짜 기준 데이터. 반환 (df, err, note)."""
    df, err = load_riders_raw(api_key, date_str)  # 서버측 날짜 필터 시도
    if err:
        return pd.DataFrame(), err, None
    note = None
    if df.empty:
        df, err = load_riders_raw(api_key, "")  # 날짜 파라미터 미지원 대비
        if err:
            return pd.DataFrame(), err, None
    if df.empty:
        return df, None, None
    if "날짜" in df.columns and df["날짜"].astype(bool).any():
        dates = df["날짜"]
        if (dates == date_str).any():
            df = df[dates == date_str]
        else:
            latest = dates[dates != ""].max()
            df = df[dates == latest]
            if latest and latest != date_str:
                note = f"선택한 날짜의 데이터가 없어 최신 제공일({latest}) 기준으로 표시합니다."
    return df.reset_index(drop=True), None, note


@st.cache_data(ttl=1800, show_spinner=False)
def load_trend(api_key: str, base_date: dt.date, station: str, days: int = TREND_DAYS):
    # 1) 전체 데이터에 여러 날짜가 포함된 경우: 클라이언트에서 집계
    full, err = load_riders_raw(api_key, "")
    if not err and full is not None and not full.empty and full["날짜"].nunique() > 1:
        sub = full[full["역명"].apply(lambda x: station_match(x, station))]
        if not sub.empty:
            g = (sub.groupby("날짜")[["승차", "하차"]].sum().reset_index()
                 .sort_values("날짜").tail(days))
            g["날짜"] = pd.to_datetime(g["날짜"], format="%Y%m%d", errors="coerce")
            return g.dropna(subset=["날짜"])
    # 2) 날짜별 개별 조회 (서버측 dt 필터 지원 시)
    recs = []
    for i in range(days):
        d = base_date - dt.timedelta(days=days - 1 - i)
        ds = d.strftime("%Y%m%d")
        df, e = load_riders_raw(api_key, ds)
        if e or df is None or df.empty:
            continue
        if "날짜" in df.columns and df["날짜"].nunique() > 1:
            df = df[df["날짜"] == ds]
            if df.empty:
                continue
        sub = df[df["역명"].apply(lambda x: station_match(x, station))]
        if sub.empty:
            continue
        recs.append({"날짜": d, "승차": int(sub["승차"].sum()),
                     "하차": int(sub["하차"].sum())})
    return pd.DataFrame(recs)


# ─────────────────────────────────────────────
# 2) 환승인원 (StationDayTrnsitNmpr, XML)
# ─────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def load_transfer(api_key: str):
    rows, err = fetch_seoul(api_key, "StationDayTrnsitNmpr", "xml", 1, 1000)
    if err:
        return pd.DataFrame(), err
    return pd.DataFrame(rows), None


# ─────────────────────────────────────────────
# 3) 혼잡도 (subwConfusion, XML)
# ─────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def load_congestion(api_key: str, station: str):
    rows, err = fetch_seoul_with_fallback(api_key, "subwConfusion", "xml", station)
    if err:
        return pd.DataFrame(), err
    return pd.DataFrame(rows), None


def detect_time_cols(df: pd.DataFrame):
    """'5시30분', 'HR_06', '_0530' 등 시간대 형태 + 숫자값 컬럼 탐지."""
    pat = re.compile(r"(\d{1,2}\s*시)|(^HR[_]?\d)|(_\d{3,4}$)|(^\d{1,2}:\d{2})", re.I)
    return [c for c in df.columns
            if pat.search(str(c)) and to_num(df[c]).notna().any()]


# ─────────────────────────────────────────────
# 4) 역사 건축 현황 (공공데이터포털 odcloud)
# ─────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def odcloud_paths():
    r = requests.get(ODCLOUD_DOCS, timeout=TIMEOUT)
    r.raise_for_status()
    return list((r.json().get("paths") or {}).keys())


@st.cache_data(ttl=3600, show_spinner=False)
def load_building(api_key: str):
    if not api_key:
        return pd.DataFrame(), "API 키가 Secrets에 설정되지 않았습니다."
    try:
        paths = odcloud_paths()
    except Exception:
        return pd.DataFrame(), "역사 건축 현황 API 명세(OAS) 조회에 실패했습니다."
    all_rows = []
    for p in paths:
        try:
            r = requests.get(
                f"{ODCLOUD_API}{p}",
                params={"page": 1, "perPage": 1000, "serviceKey": api_key},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                all_rows.extend(r.json().get("data") or [])
        except Exception:
            continue
    if not all_rows:
        return pd.DataFrame(), "역사 건축 현황 데이터를 불러오지 못했습니다. (키/권한 확인 필요)"
    return pd.DataFrame(all_rows), None


# ─────────────────────────────────────────────
# 5) 승강기 등 교통약자 시설 (SeoulMetroFaciInfo, XML)
# ─────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def load_elevator(api_key: str, station: str):
    rows, err = fetch_seoul_with_fallback(api_key, "SeoulMetroFaciInfo", "xml", station)
    if err:
        return pd.DataFrame(), err
    return pd.DataFrame(rows), None


STATION_COL_KWS = ["STTN", "STNS_NM", "STA_NM", "STN_NM", "STATION", "역명", "역사명", "역이름"]


def filter_by_station(df: pd.DataFrame, station: str, keywords=STATION_COL_KWS):
    if df.empty:
        return df
    c = find_col(df.columns, keywords)
    if not c:
        return pd.DataFrame()
    return df[df[c].apply(lambda x: station_match(str(x), station))]


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🚇 역 분석 대시보드")
    st.caption("서울교통공사 · 열린데이터광장 API 기반")

    keys = {
        "riders": get_secret("RIDERS_API_KEY"),
        "transfer": get_secret("TRANSFER_API_KEY"),
        "building": get_secret("BUILDING_API_KEY"),
        "busy": get_secret("BUSY_API_KEY"),
        "elevator": get_secret("ELEVATOR_API_KEY"),
    }

    base_date = st.date_input(
        "기준 날짜 (승하차 통계)",
        value=dt.date.today() - dt.timedelta(days=4),
        max_value=dt.date.today() - dt.timedelta(days=1),
        help="승하차 통계는 보통 3~4일 지연 제공됩니다.",
    )
    date_str = base_date.strftime("%Y%m%d")

    with st.spinner("역 목록 로딩 중..."):
        rid_df, rid_err, rid_note = load_ridership(keys["riders"], date_str)

    if not rid_df.empty:
        stations = sorted(rid_df["역명"].unique().tolist())
        search = st.text_input("역 검색", placeholder="예: 강남, 시청, 왕십리")
        filtered = ([s for s in stations if norm_station(search) in norm_station(s)]
                    if search else stations)
        if not filtered:
            st.warning("검색 결과가 없습니다. 전체 목록을 표시합니다.")
            filtered = stations
        default_idx = filtered.index("강남") if "강남" in filtered else 0
        station = st.selectbox("역 선택", filtered, index=default_idx)
    else:
        station = st.text_input("역명 직접 입력", value="강남")
        if rid_err:
            st.error(f"승하차 API: {rid_err}")

    with st.expander("🔑 API 키 설정 상태"):
        labels = {
            "riders": "승하차 (RIDERS_API_KEY · 공공데이터포털)",
            "transfer": "환승 (TRANSFER_API_KEY)",
            "building": "건축 (BUILDING_API_KEY)",
            "busy": "혼잡도 (BUSY_API_KEY)",
            "elevator": "승강기 (ELEVATOR_API_KEY)",
        }
        for k, label in labels.items():
            st.write(("✅ " if keys[k] else "❌ ") + label)
        st.caption("보안을 위해 키 값 자체는 표시되지 않습니다.")

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
st.title(f"📊 {station} 역 종합 현황")
st.caption(f"기준일: {base_date.strftime('%Y-%m-%d')} · 출처: 서울열린데이터광장 / 공공데이터포털")
if rid_note:
    st.info(rid_note)

sel = (rid_df[rid_df["역명"].apply(lambda x: station_match(x, station))]
       if not rid_df.empty else pd.DataFrame())

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

tab_ride, tab_trans, tab_busy, tab_bld, tab_elev = st.tabs(
    ["🚏 승하차 분석", "🔄 환승 인원", "📈 혼잡도", "🏗️ 역사 건축 현황", "♿ 승강기·교통약자 시설"]
)

# ── 탭1: 승하차 ──
with tab_ride:
    if rid_df.empty:
        st.warning(rid_err or "해당 날짜의 승하차 데이터가 없습니다. 다른 날짜를 선택해 보세요.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("호선별 승하차 (선택 역)")
            if sel.empty:
                st.info("선택한 역의 승하차 데이터가 없습니다.")
            else:
                m = sel.melt(id_vars=["호선"], value_vars=["승차", "하차"],
                             var_name="구분", value_name="인원")
                fig = px.bar(m, x="호선", y="인원", color="구분", barmode="group",
                             template=PLOTLY_TEMPLATE,
                             color_discrete_map={"승차": "#1C83E1", "하차": "#FF6B6B"})
                fig.update_layout(height=360, margin=dict(t=20, b=10),
                                  legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader(f"최근 {TREND_DAYS}일 이용 추이")
            with st.spinner("추이 데이터 수집 중..."):
                trend = load_trend(keys["riders"], base_date, station)
            if trend.empty:
                st.info("추이 데이터를 불러올 수 없습니다.")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=trend["날짜"], y=trend["승차"], name="승차",
                                         mode="lines+markers",
                                         line=dict(color="#1C83E1", width=3)))
                fig.add_trace(go.Scatter(x=trend["날짜"], y=trend["하차"], name="하차",
                                         mode="lines+markers",
                                         line=dict(color="#FF6B6B", width=3)))
                fig.update_layout(template=PLOTLY_TEMPLATE, height=360,
                                  margin=dict(t=20, b=10),
                                  legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

        st.subheader("전체 역 이용객 순위 (Top 20)")
        top = (rid_df.groupby("역명", as_index=False)["합계"].sum()
               .sort_values("합계", ascending=False).head(20))
        top["선택"] = top["역명"].apply(
            lambda x: "선택 역" if station_match(x, station) else "기타")
        fig = px.bar(top, x="합계", y="역명", orientation="h", color="선택",
                     template=PLOTLY_TEMPLATE,
                     labels={"합계": "총 이용객(명)"},
                     color_discrete_map={"선택 역": "#E6186C", "기타": "#B0C4DE"})
        fig.update_layout(height=560, yaxis=dict(autorange="reversed"),
                          margin=dict(t=20, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

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
                st.plotly_chart(fig, use_container_width=True)
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
                         color_discrete_map={"선택 역": "#E6186C", "기타": "#B0C4DE"})
            fig.update_layout(height=480, yaxis=dict(autorange="reversed"),
                              margin=dict(t=20, b=10), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

# ── 탭3: 혼잡도 ──
with tab_busy:
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
            meta_cols = [c for c in target.columns if c not in time_cols]
            label_col = find_col(meta_cols, ["UPDN", "방향", "DRCT", "요일", "DAY", "호선", "LINE"])
            m = target.melt(id_vars=[label_col] if label_col else None,
                            value_vars=time_cols, var_name="시간대", value_name="혼잡도")
            m["혼잡도"] = to_num(m["혼잡도"])
            m = m.dropna(subset=["혼잡도"])
            fig = px.line(m, x="시간대", y="혼잡도",
                          color=label_col if label_col else None,
                          markers=True, template=PLOTLY_TEMPLATE)
            fig.add_hline(y=100, line_dash="dash", line_color="red",
                          annotation_text="혼잡 기준(100%)")
            fig.update_layout(height=420, margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.12))
            st.plotly_chart(fig, use_container_width=True)
        st.subheader("원본 데이터")
        st.dataframe(target.head(300), use_container_width=True, hide_index=True)

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
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.metric("총 시설 수", f"{len(elev_sel)}대")
            with c2:
                st.subheader("가동/사용 상태")
                if c_use:
                    cnt = elev_sel[c_use].value_counts().reset_index()
                    cnt.columns = ["상태", "대수"]
                    fig = px.bar(cnt, x="상태", y="대수", color="상태",
                                 template=PLOTLY_TEMPLATE,
                                 color_discrete_sequence=["#00A84D", "#FF6B6B", "#B0C4DE"])
                    fig.update_layout(height=340, margin=dict(t=20, b=10),
                                      showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("상태 컬럼을 인식하지 못했습니다. 아래 표를 확인하세요.")
            st.subheader("시설 목록")
            st.dataframe(elev_sel, use_container_width=True, hide_index=True)

st.divider()
st.caption("ⓒ 서울교통공사 역 분석 대시보드 · 데이터: 서울열린데이터광장, 공공데이터포털 · API 키는 Secrets로 안전하게 관리됩니다.")
