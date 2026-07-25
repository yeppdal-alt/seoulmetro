# -*- coding: utf-8 -*-
"""
공통 모듈 (core.py)
- 모든 페이지(main.py, pages/*.py)가 함께 쓰는 데이터 로더·유틸·스타일
- 모든 API Key는 st.secrets에서 로드 (코드에 하드코딩 금지!)
"""
import re                              # 문자열 처리(정규식)
import math                            # 두 역 사이 거리 계산(하버사인)
import datetime as dt                  # 날짜 계산
import xml.etree.ElementTree as ET     # XML 응답 해석
from urllib.parse import quote         # URL에 한글을 안전하게 넣기

import pandas as pd                    # 표(데이터프레임) 처리
import requests                        # API 호출(HTTP 요청)
import streamlit as st                 # 웹 화면 프레임워크
import plotly.express as px            # 간단한 그래프
import plotly.graph_objects as go      # 세밀한 그래프

# AI용 openai 라이브러리 (없어도 대시보드는 동작)
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

SOLAR_BASE_URL = "https://api.upstage.ai/v1"
SOLAR_MODEL = "solar-open2"            # 모델 이름은 글자 그대로 사용


def page_setup(title="서울교통공사 역 분석 대시보드", icon="🚇"):
    """각 페이지 첫머리에서 호출: 페이지 설정 + 공통 CSS 적용."""
    st.set_page_config(page_title=title, page_icon=icon, layout="wide",
                       initial_sidebar_state="collapsed")
    _apply_css()


def _apply_css():
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

            /* 좌우로 나눈 칸(st.columns)을 세로로 쌓아서 그래프가 찌그러지지 않게 */
            [data-testid="stHorizontalBlock"] {flex-direction: column; gap: 0.6rem;}
            [data-testid="stHorizontalBlock"] > div {
                width: 100% !important; min-width: 100% !important; flex: 1 1 100% !important;
            }

            /* 그래프 카드의 안쪽 여백 축소 → 그래프 영역 최대화 */
            [data-testid="stPlotlyChart"] {padding: 4px;}

            /* 페이지 메뉴(라디오)가 줄바꿈되며 자연스럽게 흐르게 */
            [data-testid="stRadio"] > div {flex-wrap: wrap; gap: 4px;}
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

# 지하철 노선별 공식 색상 (지도 마커에 사용)
LINE_COLORS = {
    "1호선": "#0052A4", "2호선": "#00A84D", "3호선": "#EF7C1C", "4호선": "#00A5DE",
    "5호선": "#996CAC", "6호선": "#CD7C2F", "7호선": "#747F00", "8호선": "#E6186C",
    "9호선": "#BDB092", "경의중앙선": "#77C4A3", "공항철도": "#0090D2",
    "수인분당선": "#F5A200", "신분당선": "#D4003B", "우이신설선": "#B7C452",
    "경춘선": "#0C8E72", "서해선": "#8FC31F", "인천1호선": "#7CA8D5",
    "인천2호선": "#ED8B00", "GTX-A": "#9A6292",
}


def show_chart(fig):
    """모든 차트를 모바일에서도 깨지지 않게 공통 설정으로 출력한다.
    - 좌우 여백 최소화, 글자 크기 통일
    - responsive 설정: 화면 크기가 바뀌면 그래프도 다시 그려짐"""
    fig.update_layout(margin=dict(l=10, r=10), font=dict(size=12), autosize=True)
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "responsive": True})


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


# ─────────────────────────────────────────────
# 1-b) 2025년 승하차 보완 데이터 (첨부 CSV)
#      서울교통공사_역별 일별 시간대별 승하차인원 (2025-01-01 ~ 2025-12-31)
# ─────────────────────────────────────────────
# 압축본(.xz, 약 6.8MB)을 우선 사용하고, 없으면 원본 CSV(25MB)를 읽는다
CSV_FILE = "서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv"
CSV_CANDIDATES = (
    (CSV_FILE + ".xz", "utf-8"),   # 압축본 (utf-8로 재저장됨)
    (CSV_FILE, "cp949"),           # 원본
    (CSV_FILE, "utf-8-sig"),
)


@st.cache_data(show_spinner=False)
def load_csv_raw():
    """2025년 CSV를 읽어 원본 그대로 반환 (파일이 없으면 None).
    pandas가 .xz 압축을 자동으로 풀어서 읽어준다."""
    df = None
    for path, enc in CSV_CANDIDATES:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except (FileNotFoundError, UnicodeDecodeError):
            continue
        except Exception:
            continue
    if df is None or "수송일자" not in df.columns:
        return None
    df = df.dropna(subset=["수송일자"])            # 파일 끝의 빈 행 제거
    df["수송일자"] = df["수송일자"].astype(str).str.replace("-", "").str[:8]
    return df


@st.cache_data(show_spinner=False)
def csv_date_range():
    """CSV가 담고 있는 날짜 범위 (없으면 (None, None))."""
    raw = load_csv_raw()
    if raw is None or raw.empty:
        return None, None
    return raw["수송일자"].min(), raw["수송일자"].max()


def _csv_hour(col):
    """'06-07시간대' → '06', '06시이전' → '05', '24시이후' → '24'."""
    m = re.match(r"^(\d{2})-\d{2}시간대", str(col))
    if m:
        return m.group(1)
    if "이전" in str(col):
        return "05"
    if "이후" in str(col):
        return "24"
    return None


@st.cache_data(show_spinner=False)
def load_csv_period(date_strs: tuple, station: str = ""):
    """CSV에서 기간+역 데이터를 API와 같은 표준 형태
    (날짜/호선/역명/시간/승차/하차/합계)로 변환해 반환."""
    raw = load_csv_raw()
    if raw is None:
        return pd.DataFrame()
    sub = raw[raw["수송일자"].isin(date_strs)]
    if station:
        sub = sub[sub["역명"].apply(lambda x: station_match(str(x), station))]
    if sub.empty:
        return pd.DataFrame()
    time_cols = [c for c in sub.columns if _csv_hour(c)]
    # 시간대 컬럼(가로) → 행(세로)으로 펼치기
    m = sub.melt(id_vars=["수송일자", "호선", "역명", "승하차구분"],
                 value_vars=time_cols, var_name="시간대", value_name="인원")
    m["시간"] = m["시간대"].map(_csv_hour)
    m["인원"] = to_num(m["인원"]).fillna(0)
    # 승차/하차 행을 옆으로 나란히 붙이기
    p = (m.pivot_table(index=["수송일자", "호선", "역명", "시간"],
                       columns="승하차구분", values="인원", aggfunc="sum")
         .reset_index())
    for col in ("승차", "하차"):
        if col not in p.columns:
            p[col] = 0
    out = pd.DataFrame({
        "날짜": p["수송일자"].astype(str),
        "호선": p["호선"].astype(str),
        "역명": p["역명"].astype(str),
        "시간": p["시간"].astype(str),
        "승차": to_num(p["승차"]).fillna(0).astype(int),
        "하차": to_num(p["하차"]).fillna(0).astype(int),
    })
    out["합계"] = out["승차"] + out["하차"]
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def load_ridership_period(api_key: str, date_strs: tuple, station: str = ""):
    """여러 날짜(일별/월별/기간) 조회.
    2025년 → 첨부 CSV, 최근 일주일 → 실시간 API에서 가져와 합친다.
    반환 (df, err, note)."""
    cmin, cmax = csv_date_range()
    csv_dates = tuple(ds for ds in date_strs if cmin and cmin <= ds <= cmax)
    api_min = (dt.date.today() - dt.timedelta(days=7)).strftime("%Y%m%d")
    frames, first_err = [], None

    # 1) CSV 범위(2025년)
    if csv_dates:
        df = load_csv_period(csv_dates, station)
        if not df.empty:
            frames.append(df)

    # 2) API 범위(최근 일주일) — CSV로 못 채운 날짜만
    for ds in date_strs:
        if ds in set(csv_dates) or ds < api_min:
            continue
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
                "조회 기간에 데이터가 없습니다. (2025년: 첨부 CSV / 최근 일주일: 실시간 API 제공)")
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
    """기준일 직전 N일 승하차 추이. 2025년 날짜는 CSV, 최근 일주일은 API에서 수집."""
    date_strs = tuple((base_date - dt.timedelta(days=days - 1 - i)).strftime("%Y%m%d")
                      for i in range(days))
    cmin, cmax = csv_date_range()
    csv_dates = tuple(ds for ds in date_strs if cmin and cmin <= ds <= cmax)
    api_min = (dt.date.today() - dt.timedelta(days=7)).strftime("%Y%m%d")
    recs = []
    # 1) CSV에서 한 번에
    if csv_dates:
        df = load_csv_period(csv_dates, station)
        if not df.empty:
            g = df.groupby("날짜")[["승차", "하차"]].sum().reset_index()
            for _, r in g.iterrows():
                recs.append({"날짜": dt.datetime.strptime(r["날짜"], "%Y%m%d").date(),
                             "승차": int(r["승차"]), "하차": int(r["하차"])})
    # 2) 나머지는 API에서 날짜별로
    for ds in date_strs:
        if ds in set(csv_dates) or ds < api_min:
            continue
        df, e = load_riders_raw(api_key, ds, station)
        if e or df is None or df.empty:
            continue
        sub = df[df["역명"].apply(lambda x: station_match(x, station))]
        if sub.empty:
            continue
        recs.append({"날짜": dt.datetime.strptime(ds, "%Y%m%d").date(),
                     "승차": int(sub["승차"].sum()), "하차": int(sub["하차"].sum())})
    if not recs:
        return pd.DataFrame()
    return pd.DataFrame(recs).sort_values("날짜").reset_index(drop=True)


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
    """혼잡도(subwConfusion) 조회.
    데이터가 요일×상하행×역 조합이라 1,000행을 넘으므로 여러 페이지를 수집한다."""
    # 1) 역명을 추가 파라미터로 지원하는 경우 (한 번에 끝)
    rows, err = fetch_seoul(api_key, "subwConfusion", "xml", 1, 1000, (station,))
    if rows:
        return pd.DataFrame(rows), None
    # 2) 전체 데이터를 페이지 단위로 수집 (최대 5,000행)
    all_rows, err = [], None
    for start in range(1, 5001, 1000):
        rows, err = fetch_seoul(api_key, "subwConfusion", "xml", start, start + 999)
        if err or not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 1000:      # 마지막 페이지
            break
    if not all_rows:
        return pd.DataFrame(), err
    return pd.DataFrame(all_rows), None


def detect_time_cols(df: pd.DataFrame):
    """'TIME0530', '5시30분', 'HR_06' 등 시간대 형태 + 숫자값 컬럼 탐지."""
    pat = re.compile(r"(^TIME\d{3,4}$)|(\d{1,2}\s*시)|(^HR[_]?\d)|(_\d{3,4}$)|(^\d{1,2}:\d{2})",
                     re.I)
    return [c for c in df.columns
            if pat.search(str(c)) and to_num(df[c]).notna().any()]


def pretty_time_label(col):
    """'TIME0530' → '05:30' 처럼 읽기 쉬운 시간 표기로 변환."""
    m = re.match(r"^TIME(\d{2})(\d{2})$", str(col), re.I)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    return str(col)


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


# 역 '이름' 컬럼 후보 (혼잡도 API의 출발역 컬럼 DPTRE_STTN 포함)
STATION_COL_KWS = ["DPTRE_STTN", "STTN_NM", "STNS_NM", "STA_NM", "STN_NM",
                   "STATION", "역명", "역사명", "역이름", "STTN"]


def filter_by_station(df: pd.DataFrame, station: str, keywords=STATION_COL_KWS):
    if df.empty:
        return df
    # 역'번호'·코드 컬럼(STTN_NO 등)은 제외하고 이름 컬럼을 먼저 찾는다
    name_cols = [c for c in df.columns
                 if not re.search(r"(no|cd|code)$", str(c).lower())]
    c = find_col(name_cols, keywords) or find_col(df.columns, keywords)
    if not c:
        return pd.DataFrame()
    return df[df[c].apply(lambda x: station_match(str(x), station))]


# ─────────────────────────────────────────────
# 6) 서울시 역사 마스터 (subwayStationMaster, XML)
#    출력: BLDN_ID(역사ID), BLDN_NM(역사명), ROUTE(호선), LAT(위도), LOT(경도)
# ─────────────────────────────────────────────
def _norm_route(r: str) -> str:
    """'01호선' → '1호선' 처럼 호선 이름을 표준화."""
    r = str(r).strip()
    return re.sub(r"^0(\d)", r"\1", r)


@st.cache_data(ttl=86400, show_spinner=False)
def load_station_master(api_key: str):
    """전체 역의 이름·호선·좌표를 가져온다. 반환 (df, err)."""
    all_rows, err = [], None
    for start in (1, 1001):                     # 전체 역사는 1,000건 안팎
        rows, err = fetch_seoul(api_key, "subwayStationMaster", "xml",
                                start, start + 999)
        if err or not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 1000:
            break
    if not all_rows:
        return pd.DataFrame(), err
    df = pd.DataFrame(all_rows)
    c_nm = find_col(df.columns, ["BLDN_NM", "역사명", "STTN"])
    c_route = find_col(df.columns, ["ROUTE", "호선", "LINE"])
    c_lat = find_col(df.columns, ["LAT", "위도"])
    c_lot = find_col(df.columns, ["LOT", "LON", "경도"])
    if not all([c_nm, c_route, c_lat, c_lot]):
        return pd.DataFrame(), "역사 마스터 컬럼 구조를 인식할 수 없습니다."
    out = pd.DataFrame({
        "역명": df[c_nm].astype(str),
        "호선": df[c_route].astype(str).map(_norm_route),
        "위도": to_num(df[c_lat]),
        "경도": to_num(df[c_lot]),
    }).dropna(subset=["위도", "경도"])
    return out.reset_index(drop=True), None


def haversine_km(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 거리(km)를 하버사인 공식으로 계산."""
    R = 6371.0                                   # 지구 반지름(km)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_keys():
    """모든 API 키를 Secrets에서 한 번에 로드."""
    return {
        "riders": get_secret("RIDERS_API_KEY"),      # 승하차 (공공데이터포털)
        "transfer": get_secret("TRANSFER_API_KEY"),  # 환승
        "building": get_secret("BUILDING_API_KEY"),  # 역사 건축
        "busy": get_secret("BUSY_API_KEY"),          # 혼잡도
        "elevator": get_secret("ELEVATOR_API_KEY"),  # 승강기
        "map": get_secret("MAP_API_KEY"),            # 역사 마스터(좌표)
    }


def date_bounds():
    """조회 가능 날짜 범위: (최소일, 최대일=어제, API 최소일=7일 전)."""
    today = dt.date.today()
    api_min = today - dt.timedelta(days=7)
    max_day = today - dt.timedelta(days=1)
    cmin, _ = csv_date_range()
    min_day = dt.datetime.strptime(cmin, "%Y%m%d").date() if cmin else api_min
    return min_day, max_day, api_min


def get_stations(keys):
    """전체 역 목록 확보: API 스냅샷 → 실패 시 첨부 CSV."""
    _, max_day, _ = date_bounds()
    rid_df, rid_err = load_station_list(keys["riders"], max_day.strftime("%Y%m%d"))
    stations = []
    if not rid_df.empty:
        stations = sorted(rid_df["역명"].unique().tolist())
    else:
        raw = load_csv_raw()
        if raw is not None and "역명" in raw.columns:
            stations = sorted(raw["역명"].astype(str).unique().tolist())
    return stations, rid_df, rid_err


def select_period(prefix: str = "main"):
    """일별/월별/기간 설정 위젯을 그리고 (mode, date_list, period_label)을 돌려준다."""
    MIN_DAY, MAX_DAY, _ = date_bounds()
    mode = st.radio("조회 방식", ["일별", "월별", "기간 설정"],
                    horizontal=True, key=f"{prefix}_mode")
    date_list = []          # 조회할 날짜들(dt.date 리스트)
    period_label = ""       # 화면에 보여줄 기간 문구

    if mode == "일별":
        d = st.date_input("날짜", value=MAX_DAY, min_value=MIN_DAY,
                          max_value=MAX_DAY, key=f"{prefix}_day")
        date_list = [d]
        period_label = d.strftime("%Y-%m-%d")

    elif mode == "월별":
        # 2025-01부터 이번 달까지 모두 선택 가능 (최신 달이 먼저 보이게)
        months = []
        _m = MAX_DAY.replace(day=1)
        _stop = MIN_DAY.replace(day=1)
        while _m >= _stop:
            months.append(_m.strftime("%Y-%m"))
            _m = (_m - dt.timedelta(days=1)).replace(day=1)
        month_sel = st.selectbox("월 선택", months, key=f"{prefix}_month")
        y, m = map(int, month_sel.split("-"))
        d0 = dt.date(y, m, 1)
        d1 = (dt.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
              - dt.timedelta(days=1))                      # 그 달의 마지막 날
        s, e = max(d0, MIN_DAY), min(d1, MAX_DAY)          # 제공 범위와 교집합
        if s <= e:
            date_list = [s + dt.timedelta(days=i) for i in range((e - s).days + 1)]
        period_label = month_sel

    else:  # 기간 설정
        rng = st.date_input("기간 (시작 ~ 종료)",
                            value=(max(MIN_DAY, MAX_DAY - dt.timedelta(days=6)), MAX_DAY),
                            min_value=MIN_DAY, max_value=MAX_DAY, key=f"{prefix}_range")
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

    st.caption("ℹ️ **2025년 데이터**는 첨부된 통계 파일에서, **최근 일주일**은 실시간 API에서 조회합니다. "
               "2026년 중 일주일 이전 날짜는 두 데이터의 제공 범위 밖이라 조회되지 않아요.")
    return mode, date_list, period_label


def solar_stream_answer(messages):
    """Upstage Solar(solar-open2)를 스트리밍으로 호출해 답변을 화면에 흘려보낸다.
    - reasoning_effort='none' → 추론 기능을 꺼서 빠르게 응답
    - 실패하면 무서운 에러 화면 대신 친절한 한국어 안내를 보여주고 None 반환"""
    solar_key = get_secret("SOLAR_API_KEY")
    if OpenAI is None:
        st.info("openai 라이브러리가 필요해요. requirements.txt로 설치해 주세요.")
        return None
    if not solar_key:
        st.info("Secrets에 SOLAR_API_KEY를 등록하면 AI 기능을 사용할 수 있어요.")
        return None
    try:
        client = OpenAI(api_key=solar_key, base_url=SOLAR_BASE_URL)
        common = dict(model=SOLAR_MODEL, messages=messages, stream=True)
        try:
            stream = client.chat.completions.create(reasoning_effort="none", **common)
        except TypeError:   # 구버전 openai 라이브러리 대비
            stream = client.chat.completions.create(
                extra_body={"reasoning_effort": "none"}, **common)

        def token_stream():
            for chunk in stream:
                if chunk.choices:
                    piece = chunk.choices[0].delta.content
                    if piece:
                        yield piece

        return st.write_stream(token_stream())
    except Exception:
        st.warning("죄송해요, 지금은 AI 답변을 받아오지 못했어요. 😥\n\n"
                   "잠시 후 다시 시도해 주세요. 계속 안 되면 SOLAR_API_KEY가 "
                   "올바른지, 인터넷 연결이 되어 있는지 확인해 주세요.")
        return None
