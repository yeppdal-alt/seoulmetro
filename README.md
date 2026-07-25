# 🚇 지하철 인사이트 랩 — 서울교통공사 역 분석 대시보드

서울 지하철 역별 승하차인원 · 환승인원 · 혼잡도 · 역사 건축 현황 · 승강기(교통약자 시설)를
역명 기준으로 통합 분석하고, Upstage Solar AI로 비교 분석·휴가 요일 추천·미래 수요 예측까지
제공하는 Streamlit 멀티페이지 대시보드입니다.

## 페이지 구성

| 페이지 | 내용 |
|---|---|
| **main.py** (메인) | 📊 역 종합 현황 · 📈 혼잡도 · 🗺️ 주변 역 지도 (상단 버튼으로 전환) |
| **pages/00_AI분석기.py** | 🥊 역 대 역 — AI 비교 분석실 (관심역 최대 3곳 비교 + AI 채팅) |
| **pages/01_예측도우미.py** | 🏖️ 휴가 타이밍 예측기 (요일 분석 + 미래 날짜 승차 예측 + AI 추천) |

## 폴더 구조

```
seoul-metro-dashboard/
├── main.py                          # 메인: 역 종합 현황 / 혼잡도 / 주변 역 지도
├── core.py                          # 공통 모듈: 데이터 로더·유틸·스타일·Solar API
├── pages/
│   ├── 00_AI분석기.py               # 관심역 비교 분석 + AI 도우미 채팅
│   └── 01_예측도우미.py             # 휴가 요일 추천 + 미래 승차 예측
├── 서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv(.xz)
│                                    # 2025년 승하차 통계 (원본 25MB 또는 압축본 6.8MB)
├── requirements.txt                 # openai / plotly / requests
├── .gitignore                       # secrets.toml 커밋 방지
└── .streamlit/
    └── secrets.toml.example         # 키 설정 예시 (복사해서 secrets.toml 생성)
```

## 데이터 소스

| 데이터 | 출처 / Endpoint | 키 |
|---|---|---|
| 역별 승하차인원 (시간대별, 최근 일주일) | 공공데이터포털 `apis.data.go.kr/B553766/psgr/getStnPsgr` | `RIDERS_API_KEY` |
| 2025년 승하차 통계 (역별·일별·시간대별) | 첨부 CSV — 폴더에서 자동 탐색, 인코딩 자동 판별 | 불필요 |
| 환승역 환승인원 | 서울열린데이터광장 `StationDayTrnsitNmpr` | `TRANSFER_API_KEY` |
| 지하철 혼잡도 (30분 단위, 평일/토/일) | 서울열린데이터광장 `subwConfusion` | `BUSY_API_KEY` |
| 역사 건축 현황 | 공공데이터포털 odcloud (OAS 자동 탐색) | `BUILDING_API_KEY` |
| 승강기·교통약자 시설 | 서울열린데이터광장 `SeoulMetroFaciInfo` | `ELEVATOR_API_KEY` |
| 역사 마스터 (역명·호선·좌표) | 서울열린데이터광장 `subwayStationMaster` | `MAP_API_KEY` |
| AI (채팅·추천) | Upstage Solar `solar-open2` — 추론 off, 스트리밍 | `SOLAR_API_KEY` |

> 혼잡도: 서울교통공사 1~8호선 30분 단위 평균 혼잡도. 정원 대비 승차 인원 비율로,
> 좌석 수만큼 승차 시 34%, 100% = 정원 기준 만차. 2024년부터 분기별 제공.

## Secrets 설정

### 로컬 실행 시
`.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사하고 실제 키 입력:

```toml
RIDERS_API_KEY   = "공공데이터포털 일반 인증키 (역별승하차인원정보 B553766/psgr 활용신청)"
TRANSFER_API_KEY = "서울열린데이터광장 인증키"
BUILDING_API_KEY = "공공데이터포털 인증키 (역사 건축 현황, Decoding 키)"
BUSY_API_KEY     = "서울열린데이터광장 인증키"
ELEVATOR_API_KEY = "서울열린데이터광장 인증키"
MAP_API_KEY      = "서울열린데이터광장 인증키 (역사 마스터·지도)"
SOLAR_API_KEY    = "Upstage Solar API 키 (https://console.upstage.ai)"
```

- 서울열린데이터광장(https://data.seoul.go.kr) 키는 하나로 여러 서비스에 공용 사용 가능
- 공공데이터포털(https://www.data.go.kr)은 각 데이터셋 활용신청 후 일반 인증키 사용

### Streamlit Cloud 배포 시
앱 설정 → **Settings → Secrets**에 위 TOML 내용을 그대로 붙여넣기.
(`secrets.toml` 파일은 절대 GitHub에 올리지 않습니다 — .gitignore가 막아줍니다)

## 실행 및 배포

```bash
pip install -r requirements.txt
streamlit run main.py
```

Streamlit Cloud 배포:

1. 폴더 전체를 GitHub 저장소로 push — `core.py`, `pages/`, CSV 파일 포함 (웹 업로드는 25MB 제한이 있어 압축본 `.csv.xz` 권장)
2. https://share.streamlit.io → **New app** → Main file path: `main.py`
3. **Advanced settings → Secrets**에 7개 키 붙여넣기 → **Deploy**
4. 코드/파일 변경 후에는 앱 **Reboot**

## 주요 기능

**메인 — 역 종합 현황**: 역 검색·선택(최상단), 조회 기간(일별/최근 일주일 누적),
KPI 카드(승차·하차·총 이용객·환승), 시간대별 승하차, 호선별 비교, 최근 7일 추이,
전체 역 Top 20, 환승·건축·승강기 탭.

**메인 — 혼잡도**: 30분 단위 시간대별 혼잡도 라인차트(요일·상하행 구분, 100% 기준선),
데이터 출처·산정 기준 안내, 원본 데이터 표.

**메인 — 주변 역 지도**: 역사 마스터 좌표 기반 반경(0.5~3km) 내 역 탐색,
호선 색상 마커 + 역명 라벨 Plotly 지도(토큰 불필요), 주변 역 목록,
가까운 역 최대 6곳 혼잡도 히트맵 비교.

**AI분석기**: 관심역 최대 3곳의 승하차·시간대 패턴·일별 추이·혼잡도 나란히 비교 +
Solar AI 채팅(대화 기억, 스트리밍 답변).

**예측도우미**: 2025년 통계로 요일별 평균 이용객 분석(한산한/붐비는 평일),
미래 날짜 선택 시 같은 달×같은 요일 패턴 기반 승차인원 예측(예상 범위·시간대 패턴 포함),
Solar AI의 휴가 요일 추천.

**공통**: 소프트 모던 UI(비비드 블루·화이트 카드·알약 버튼), 모바일 반응형(컬럼 세로 쌓기,
차트 자동 리사이즈), API 오류·데이터 없음·로딩 상태 처리, 응답 캐시(10~30분),
승하차 데이터는 2025년 CSV + 최근 일주일 실시간 API 자동 전환.

## 보안

- 모든 API 키는 `st.secrets`에서만 로드 (코드에 하드코딩 없음)
- 키 값은 화면·로그·에러 메시지에 노출되지 않음
- AI 요청 실패 시 친절한 한국어 안내로 대체 (원본 에러 미노출)
