# -*- coding: utf-8 -*-
"""
서울교통공사 역 분석 대시보드 (main.py)
- 승하차인원 / 환승인원 / 혼잡도 / 역사 건축 현황 / 승강기(교통약자 시설)
- AI 분석 도우미: Upstage Solar API (모델 solar-open2, openai 라이브러리 사용)
- 모든 API Key는 st.secrets에서 로드 (코드에 하드코딩 금지!)
- 실행: streamlit run main.py
"""
import re                              # 문자열에서 괄호 등을 제거할 때 사용
import datetime as dt                  # 날짜 계산용
import xml.etree.ElementTree as ET     # XML 응답 해석용
from urllib.parse import quote         # URL에 한글을 안전하게 넣기 위한 도구

import pandas as pd                    # 표(데이터프레임) 처리
import requests                        # API 호출(HTTP 요청)
import streamlit as st                 # 웹 화면을 만드는 프레임워크
import plotly.express as px            # 간단한 그래프
import plotly.graph_objects as go      # 세밀하게 조절하는 그래프

# AI 챗봇용 openai 라이브러리 (설치가 안 돼 있어도 대시보드는 동작하도록 처리)
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ─────────────────────────────────────────────
# 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="서울교통공사 역 분석 대시보드",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="collapsed",  # 사이드바 없이 한 화면으로 구성
)

# ── 화면을 세련되게 꾸미는 CSS (소프트 스카이블루 톤, 흰색 라운드 카드) ──
st.markdown(
    """
    <style>
    /* 한국어에 잘 어울리는 Pretendard 글꼴 불러오기 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {font-family: 'Pretendard', sans-serif;}

    /* 전체 배경: 아주 연한 하늘색 그라데이션 */
    .stApp {
        background: linear-gradient(180deg, #EAF3FF 0%, #F5FAFF 45%, #F2F8FF 100%);
    }
    /* 스트림릿 기본 상단바를 투명하게 → 배경과 자연스럽게 연결 */
    [data-testid="stHeader"] {background: transparent;}

    /* 상단 여백을 넉넉히 → 제목 글자가 짤리지 않게 */
    .block-container {padding-top: 3rem; padding-bottom: 2.5rem; max-width: 1150px;}

    /* 제목 계열 글자색: 짙은 네이비 */
    h1, h2, h3 {color: #0F3D6E !important; letter-spacing: -0.4px;}

    /* 상단 히어로 배너: 밝은 하늘색 카드 + 어두운 글자 */
    .hero {
        background: linear-gradient(120deg, #CFE6FF 0%, #E4F0FF 55%, #F2F8FF 100%);
        border: 1px solid #FFFFFF;
        border-radius: 24px; padding: 26px 30px; margin: 6px 0 10px 0;
        box-shadow: 0 12px 30px rgba(59, 157, 248, 0.16);
    }
    .hero-title {font-size: 1.9rem; font-weight: 800; color: #0F3D6E; letter-spacing: -0.5px;}
    .hero-title span {font-weight: 500; color: #3D6C9E;}
    .hero-sub {margin-top: 6px; font-size: 0.9rem; color: #5B7FA6;}

    /* KPI 지표 카드: 흰색 + 큰 라운드 + 은은한 그림자 */
    [data-testid="stMetric"] {
        background: #FFFFFF; border: none;
        border-radius: 20px; padding: 16px 20px;
        box-shadow: 0 8px 22px rgba(59, 157, 248, 0.10);
        transition: transform .15s ease;
    }
    [data-testid="stMetric"]:hover {transform: translateY(-2px);}
    [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #5B7FA6;}
    [data-testid="stMetricValue"] {color: #0F3D6E;}

    /* 탭: 흰색 알약 → 선택되면 하늘색 채움 */
    .stTabs [data-baseweb="tab-list"] {gap: 8px; flex-wrap: wrap;}
    .stTabs [data-baseweb="tab"] {
        border-radius: 999px; padding: 8px 18px;
        background: #FFFFFF;
        box-shadow: 0 2px 10px rgba(59, 157, 248, 0.08);
    }
    .stTabs [aria-selected="true"] {
        background: #3B9DF8 !important; color: #FFFFFF !important;
    }

    /* 그래프도 흰색 라운드 카드 위에 얹기 */
    [data-testid="stPlotlyChart"] {
        background: #FFFFFF; border-radius: 20px; padding: 12px;
        box-shadow: 0 8px 22px rgba(59, 157, 248, 0.10);
    }

    /* 입력창·선택창: 둥근 모서리 + 흰 배경 */
    [data-testid="stTextInput"] input, [data-testid="stDateInput"] input {
        border-radius: 999px; background: #FFFFFF;
    }
    [data-baseweb="select"] > div {border-radius: 999px; background: #FFFFFF;}

    /* 버튼: 하늘색 알약 */
    .stButton > button {
        border-radius: 999px; border: none;
        background: #3B9DF8; color: #FFFFFF; padding: 8px 22px;
        box-shadow: 0 6px 16px rgba(59, 157, 248, 0.28);
    }
    .stButton > button:hover {background: #2F8BE0; color: #FFFFFF;}

    /* 펼침 메뉴(expander)·채팅 말풍선·표: 흰색 라운드 카드 */
    [data-testid="stExpander"] {
        background: #FFFFFF; border: none; border-radius: 18px;
        box-shadow: 0 4px 14px rgba(59, 157, 248, 0.08);
    }
    [data-testid="stChatMessage"] {
        background: #FFFFFF; border-radius: 18px; padding: 8px 14px;
        box-shadow: 0 4px 14px rgba(59, 157, 248, 0.08);
        margin-bottom: 6px;
    }
    [data-testid="stDataFrame"] {
        background: #FFFFFF; border-radius: 16px; padding: 6px;
        box-shadow: 0 4px 14px rgba(59, 157, 248, 0.08);
    }

    /* 안내 박스도 라운드하게 */
    [data-testid="stAlert"] {border-radius: 16px;}

    /* 모바일(좁은 화면) 대응 */
    @media (max-width: 640px) {
        [data-testid="stMetricValue"] {font-size: 1.25rem;}
        .hero-title {font-size: 1.3rem;}
        .block-container {padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 2.6rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SEOUL_BASE = "http://openapi.seoul.go.kr:8088"
ODCLOUD_DOCS = "https://infuser.odcloud.kr/oas/docs?namespace=15044258/v1"
ODCLOUD_API = "https://api.odcloud.kr/api"
TIMEOUT = 12
TREND_DAYS = 7  # 승하차 API가 최근 일주일 데이터만 제공

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
# Endpoint: https://apis.data.go.kr/B553766/psgr (상세기능: 역별승하차인원정보 조회)
RIDERS_BASE = "https://apis.data.go.kr/B553766/psgr"
RIDERS_ENDPOINT = f"{RIDERS_BASE}/getStnPsgr"


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
def _fetch_riders_page(api_key: str, page: int, num_rows: int,
                       pasng_ymd: str = "", stn_nm: str = "", pasng_hr: str = ""):
    """getStnPsgr 호출. 반환: (rows|None, err|None, total_count)
    요청변수: serviceKey, pageNo, numOfRows, dataType,
              pasngYmd(통행일자, 최근 일주일), stnNm(역명 포함검색), pasngHr(00~23)"""
    if not api_key:
        return None, "API 키가 Secrets에 설정되지 않았습니다.", 0
    params = {"serviceKey": api_key, "pageNo": page,
              "numOfRows": num_rows, "dataType": "JSON"}
    if pasng_ymd:
        params["pasngYmd"] = pasng_ymd
    if stn_nm:
        params["stnNm"] = stn_nm
    if pasng_hr:
        params["pasngHr"] = pasng_hr
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
    """API 응답 컬럼명을 표준(날짜/호선/역명/시간/승차/하차/합계)으로 변환."""
    cols = list(df.columns)
    c_date = find_col(cols, ["pasngYmd", "useYmd", "ymd", "일자", "date"])
    c_stn = (find_col(cols, ["stnNm", "staNm", "stationNm", "역명"])
             or find_col(cols, ["stn", "sta"]))
    c_line = find_col(cols, ["lineNm", "line", "호선", "rout"])
    c_hour = find_col(cols, ["pasngHr", "hr", "시간"])
    c_ride = find_col(cols, ["ride", "gton", "승차"])
    c_alight = find_col(cols, ["algh", "alight", "gtoff", "하차"])
    if not c_stn:
        return pd.DataFrame(), "역명 컬럼 인식 실패. 응답 컬럼: " + ", ".join(map(str, cols))
    if not (c_ride and c_alight):
        # 이름으로 못 찾으면: 코드/날짜/시간성 컬럼을 제외한 숫자 컬럼 2개를 승차/하차로 간주
        nums = []
        for c in numeric_cols(df):
            name = str(c).lower()
            if c in (c_date, c_hour) or "cd" in name or name.endswith("no"):
                continue
            v = to_num(df[c])
            if pd.notna(v.max()) and v.max() > 5_000_000:
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
        "시간": (df[c_hour].astype(str).str.zfill(2) if c_hour else ""),
        "승차": to_num(df[c_ride]).fillna(0).astype(int),
        "하차": to_num(df[c_alight]).fillna(0).astype(int),
    })
    out["합계"] = out["승차"] + out["하차"]
    return out, None


@st.cache_data(ttl=1800, show_spinner=False)
def load_riders_raw(api_key: str, pasng_ymd: str = "", stn_nm: str = "",
                    pasng_hr: str = "", max_pages: int = 5):
    """페이지네이션 포함 원본 수집 → 표준 DataFrame. 반환 (df, err)."""
    all_rows = []
    for page in range(1, max_pages + 1):
        rows, err, total = _fetch_riders_page(api_key, page, 1000,
                                              pasng_ymd, stn_nm, pasng_hr)
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


@st.cache_data(ttl=1800, show_spinner=False)
def load_ridership_period(api_key: str, date_strs: tuple, station: str = ""):
    """여러 날짜(일별/월별/기간)를 합쳐서 조회. stnNm은 '포함' 검색이므로 재필터.
    반환 (df, err, note)."""
    frames, first_err = [], None
    for ds in date_strs:
        df, e = load_riders_raw(api_key, ds, station)
        if e:
            first_err = first_err or e   # 첫 에러만 기억
            continue
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        if first_err:
            return pd.DataFrame(), first_err, None
        return (pd.DataFrame(), None,
                "조회 기간에 데이터가 없습니다. (승하차 API는 최근 일주일 데이터만 제공)")
    out = pd.concat(frames, ignore_index=True)
    if station:
        out = out[out["역명"].apply(lambda x: station_match(x, station))]
    return out.reset_index(drop=True), None, None


@st.cache_data(ttl=1800, show_spinner=False)
def load_station_list(api_key: str, date_str: str):
    """역 목록 스냅샷: 08시 한 시간대만 조회해 가볍게 전체 역 목록/순위 구성.
    반환 (df, err)."""
    df, err = load_riders_raw(api_key, date_str, "", "08")
    if (df is None or df.empty) and not err:
        # pasngHr 미지원/데이터 없음 대비: 시간 필터 없이 제한적으로 조회
        df, err = load_riders_raw(api_key, date_str, "", "", max_pages=3)
    return df, err


@st.cache_data(ttl=1800, show_spinner=False)
def load_trend(api_key: str, base_date: dt.date, station: str, days: int = TREND_DAYS):
    """최근 N일(최대 일주일) 역별 승하차 추이. 날짜별 stnNm 필터 조회."""
    recs = []
    for i in range(days):
        d = base_date - dt.timedelta(days=days - 1 - i)
        ds = d.strftime("%Y%m%d")
        df, e = load_riders_raw(api_key, ds, station)
        if e or df is None or df.empty:
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
# 상단 컨트롤 (역 검색 → 조회 방식) : 좌우 구분 없이 한 화면
# ─────────────────────────────────────────────
keys = {
    "riders": get_secret("RIDERS_API_KEY"),
    "transfer": get_secret("TRANSFER_API_KEY"),
    "building": get_secret("BUILDING_API_KEY"),
    "busy": get_secret("BUSY_API_KEY"),
    "elevator": get_secret("ELEVATOR_API_KEY"),
}

# 승하차 API가 제공하는 날짜 범위: 최근 일주일 (어제 ~ 7일 전)
TODAY = dt.date.today()
MIN_DAY = TODAY - dt.timedelta(days=7)
MAX_DAY = TODAY - dt.timedelta(days=1)

st.markdown("## 🚇 서울교통공사 역 분석 대시보드")

# ── 1) 역 검색 (최상단) ──
col_search, col_select = st.columns([1, 1.6])
with st.spinner("역 목록 로딩 중..."):
    rid_df, rid_err = load_station_list(keys["riders"], MAX_DAY.strftime("%Y%m%d"))

if not rid_df.empty:
    stations = sorted(rid_df["역명"].unique().tolist())
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

# ── 2) 조회 방식: 일별 / 월별 / 기간 설정 ──
mode = st.radio("조회 방식", ["일별", "월별", "기간 설정"], horizontal=True)

date_list = []          # 조회할 날짜들(dt.date 리스트)
period_label = ""       # 화면에 보여줄 기간 문구

if mode == "일별":
    d = st.date_input("날짜", value=MAX_DAY, min_value=MIN_DAY, max_value=MAX_DAY)
    date_list = [d]
    period_label = d.strftime("%Y-%m-%d")

elif mode == "월별":
    # 이번 달 / 지난 달 중 선택 → 그 달의 날짜 중 API 제공 범위와 겹치는 날만 조회
    cur_first = MAX_DAY.replace(day=1)
    prev_first = (cur_first - dt.timedelta(days=1)).replace(day=1)
    month_sel = st.selectbox("월 선택",
                             [cur_first.strftime("%Y-%m"), prev_first.strftime("%Y-%m")])
    y, m = map(int, month_sel.split("-"))
    d0 = dt.date(y, m, 1)
    d1 = (dt.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
          - dt.timedelta(days=1))                      # 그 달의 마지막 날
    s, e = max(d0, MIN_DAY), min(d1, MAX_DAY)          # 제공 범위와 교집합
    if s <= e:
        date_list = [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]
    period_label = month_sel

else:  # 기간 설정
    rng = st.date_input("기간 (시작 ~ 종료)", value=(MIN_DAY, MAX_DAY),
                        min_value=MIN_DAY, max_value=MAX_DAY)
    # 날짜를 고르는 중에는 값이 1개만 들어올 수 있어 안전하게 처리
    if isinstance(rng, (tuple, list)):
        if len(rng) == 2:
            s, e = rng
        elif len(rng) == 1:
            s = e = rng[0]
        else:
            s = e = MAX_DAY
    else:
        s = e = rng
    date_list = [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]
    period_label = f"{s.strftime('%Y-%m-%d')} ~ {e.strftime('%Y-%m-%d')}"

st.caption("ℹ️ 승하차 API는 **최근 일주일** 데이터만 제공합니다. 그 이전 날짜는 조회 범위에서 제외돼요.")

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

tab_ride, tab_trans, tab_busy, tab_bld, tab_elev, tab_ai = st.tabs(
    ["🚏 승하차 분석", "🔄 환승 인원", "📈 혼잡도", "🏗️ 역사 건축 현황",
     "♿ 승강기·교통약자 시설", "🤖 AI 도우미"]
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
                                 marker_color="#3B9DF8"))
            fig.add_trace(go.Bar(x=hourly["시간"], y=hourly["하차"], name="하차",
                                 marker_color="#FF7E9D"))
            fig.update_layout(template=PLOTLY_TEMPLATE, barmode="group", height=380,
                              xaxis_title="시간대(시)", yaxis_title="인원(명)",
                              margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("호선별 승하차 (선택 역)")
            m = (sel.groupby("호선", as_index=False)[["승차", "하차"]].sum()
                 .melt(id_vars=["호선"], value_vars=["승차", "하차"],
                       var_name="구분", value_name="인원"))
            fig = px.bar(m, x="호선", y="인원", color="구분", barmode="group",
                         template=PLOTLY_TEMPLATE,
                         color_discrete_map={"승차": "#3B9DF8", "하차": "#FF7E9D"})
            fig.update_layout(height=360, margin=dict(t=20, b=10),
                              legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)
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
                                         line=dict(color="#3B9DF8", width=3)))
                fig.add_trace(go.Scatter(x=trend["날짜"], y=trend["하차"], name="하차",
                                         mode="lines+markers",
                                         line=dict(color="#FF7E9D", width=3)))
                fig.update_layout(template=PLOTLY_TEMPLATE, height=360,
                                  margin=dict(t=20, b=10),
                                  legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

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
                     color_discrete_map={"선택 역": "#FF5C8A", "기타": "#C9DCF0"})
        fig.update_layout(height=560, yaxis=dict(autorange="reversed"),
                          margin=dict(t=20, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
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
                         color_discrete_map={"선택 역": "#FF5C8A", "기타": "#C9DCF0"})
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
                                 color_discrete_sequence=["#00A84D", "#FF7E9D", "#C9DCF0"])
                    fig.update_layout(height=340, margin=dict(t=20, b=10),
                                      showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("상태 컬럼을 인식하지 못했습니다. 아래 표를 확인하세요.")
            st.subheader("시설 목록")
            st.dataframe(elev_sel, use_container_width=True, hide_index=True)

# ── 탭6: AI 도우미 (Upstage Solar API, 모델 solar-open2) ──
with tab_ai:
    st.subheader("🤖 AI 분석 도우미")
    st.caption("역 데이터에 대해 궁금한 점을 물어보세요. 이전 대화를 기억하며 이어서 답해요.")

    # 1) Secrets에서 Solar API 키를 불러온다 (코드에 키를 직접 쓰지 않는다!)
    solar_key = get_secret("SOLAR_API_KEY")

    if OpenAI is None:
        # openai 라이브러리가 설치되지 않은 경우
        st.info("openai 라이브러리가 필요해요. 터미널에서 `pip install openai` 후 다시 실행해 주세요.")
    elif not solar_key:
        # 키가 등록되지 않은 경우
        st.info("Secrets에 SOLAR_API_KEY를 등록하면 AI 도우미를 사용할 수 있어요.")
    else:
        # 2) 대화 기록을 세션(session_state)에 저장 → 새로고침 전까지 기억
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []   # [{"role": "user"/"assistant", "content": "..."}]

        # 대화를 처음부터 다시 시작하고 싶을 때 누르는 버튼
        if st.session_state.chat_messages and st.button("🗑️ 대화 지우기"):
            st.session_state.chat_messages = []
            st.rerun()

        # 3) 지금까지의 대화를 말풍선으로 다시 그려준다
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # 4) 채팅 입력창 (화면 아래에 고정됨)
        user_input = st.chat_input("예: 이 역은 몇 시에 제일 붐비나요?")

        if user_input:
            # (1) 사용자의 말을 기록하고 말풍선으로 표시
            st.session_state.chat_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # (2) AI에게 줄 성격(시스템 프롬프트) + 현재 화면 정보(참고용)
            system_prompt = "너는 따뜻하고 친절한 데이터 분석 선생님이야. 반드시 순수 한국어로만 답해"
            context = f"[참고 정보] 사용자가 보고 있는 역: {station}, 기준일: {base_date.strftime('%Y-%m-%d')}"
            if not sel.empty:
                context += (f", 이날 승차 {int(sel['승차'].sum()):,}명 / "
                            f"하차 {int(sel['하차'].sum()):,}명")

            # 시스템 프롬프트 → 참고 정보 → 지금까지의 대화 순서로 전달
            messages = ([{"role": "system", "content": system_prompt},
                         {"role": "system", "content": context}]
                        + st.session_state.chat_messages)

            # (3) Solar API를 호출하고, 답을 글자 단위로 실시간 표시(스트리밍)
            answer = None
            with st.chat_message("assistant"):
                try:
                    # openai 라이브러리로 Upstage Solar 서버에 접속
                    client = OpenAI(api_key=solar_key,
                                    base_url="https://api.upstage.ai/v1")
                    common = dict(
                        model="solar-open2",     # 모델 이름은 글자 그대로 사용
                        messages=messages,
                        stream=True,             # 스트리밍(실시간 출력) 켜기
                    )
                    try:
                        # 추론(생각) 기능 끄기 → 답이 빨리 나온다
                        stream = client.chat.completions.create(
                            reasoning_effort="none", **common)
                    except TypeError:
                        # 구버전 openai 라이브러리 대비: extra_body로 전달
                        stream = client.chat.completions.create(
                            extra_body={"reasoning_effort": "none"}, **common)

                    # 스트리밍 조각(chunk)에서 글자만 뽑아 흘려보내는 함수
                    def token_stream():
                        for chunk in stream:
                            if chunk.choices:
                                piece = chunk.choices[0].delta.content
                                if piece:
                                    yield piece

                    # st.write_stream: 글자가 실시간으로 흘러나오듯 표시
                    answer = st.write_stream(token_stream())
                except Exception:
                    # 실패해도 무서운 에러 화면 대신 친절한 한국어 안내만 보여준다
                    st.warning(
                        "죄송해요, 지금은 AI 답변을 받아오지 못했어요. 😥\n\n"
                        "잠시 후 다시 시도해 주세요. 계속 안 되면 SOLAR_API_KEY가 "
                        "올바른지, 인터넷 연결이 되어 있는지 확인해 주세요."
                    )

            # (4) AI의 답도 대화 기록에 저장 → 다음 질문에서 문맥을 기억
            if answer:
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": answer})

st.divider()
st.caption("ⓒ 서울교통공사 역 분석 대시보드 · 데이터: 서울열린데이터광장, 공공데이터포털 · AI: Upstage Solar · API 키는 Secrets로 안전하게 관리됩니다.")
