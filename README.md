# 🚇 서울교통공사 역 분석 대시보드

역별 승하차인원 · 환승인원 · 혼잡도 · 역사 건축 현황 · 승강기(교통약자 시설)를
역명 기준으로 통합해 한 화면에서 비교·분석하는 Streamlit 대시보드입니다.

## 폴더 구조

```
seoul-metro-dashboard/
├── app.py                          # 메인 앱 (전체 코드)
├── requirements.txt
├── .gitignore                      # secrets.toml 커밋 방지
└── .streamlit/
    └── secrets.toml.example        # 키 설정 예시 (복사해서 secrets.toml 생성)
```

## Secrets 설정

### 로컬 실행 시
`.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사하고 실제 키 입력:

```toml
RIDERS_API_KEY   = "서울열린데이터광장 인증키"
TRANSFER_API_KEY = "서울열린데이터광장 인증키"
BUILDING_API_KEY = "공공데이터포털(data.go.kr) 인증키 (Decoding 키)"
BUSY_API_KEY     = "서울열린데이터광장 인증키"
ELEVATOR_API_KEY = "서울열린데이터광장 인증키"
```

- 서울열린데이터광장 키 발급: https://data.seoul.go.kr (하나의 키를 여러 서비스에 공용 사용 가능)
- 공공데이터포털 키 발급: https://www.data.go.kr → "서울교통공사 역사 건축 현황" 활용신청

### Streamlit Cloud 배포 시
앱 설정 → **Settings → Secrets**에 위 TOML 내용을 그대로 붙여넣기.
(secrets.toml 파일은 절대 GitHub에 올리지 않습니다)

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 배포

1. 이 폴더를 GitHub 저장소로 push (`secrets.toml` 제외 — .gitignore가 막아줌)
2. https://share.streamlit.io 접속 → **New app**
3. 저장소/브랜치 선택, Main file path: `app.py`
4. **Advanced settings → Secrets**에 5개 키 붙여넣기
5. **Deploy** 클릭

## 기능

- 역 검색/선택 (사이드바), 날짜 선택
- KPI: 승차·하차·총 이용객·환승 인원
- 승하차: 호선별 비교, 최근 14일 추이, 전체 역 Top 20 순위
- 환승: 선택 역 환승 규모 + 상위 15개 환승역 비교
- 혼잡도: 시간대별 혼잡도 라인차트 (100% 기준선 표시)
- 건축 현황: 역별 건축 정보 카드 + 검색
- 승강기: 종류별/가동상태별 시각화 + 시설 목록
- API 오류·데이터 없음·로딩 상태 모두 처리, 응답은 30분 캐시

## 보안

- 모든 API 키는 `st.secrets`에서만 로드 (하드코딩 없음)
- 키 값은 화면·로그·에러 메시지에 노출되지 않음
- 사이드바에서 키 설정 여부(✅/❌)만 확인 가능
