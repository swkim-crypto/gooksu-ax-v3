# ADB 세미나 대응 변경 (2026-11-23)

## 1. 원시데이터 설명 (시작 화면 좌측 '원시데이터 보기' 버튼)
- static/rawdata/ : rawdata.js·css, cases.json(사례 6건 한/영), manifest.json(현재 **샘플**)
- tools/make_rawdata_manifest.py : 내 PC 원본 폴더 → manifest.json (파일 목록만, 내용 미열람)
- 캡처: static/rawdata/img/ 에 cases.json의 파일명대로 (01_pdf_garbled.png 등 8장, 일부만 있어도 동작)
- `?rawdata=1` 로 접속하면 모달이 바로 열림

## 2. 한/EN 토글 (좌측 상단, 팝아웃 창 헤더)
- static/i18n.js, static/i18n_dict.js : UI 문구
- static/i18n/en.json : 데이터 값 사전 (장비 64·계통·매체·사양 60·아이소·품명·도면 용어) — 프론트/백엔드 공용
- i18n_en.py : 백엔드 번역기 (en.json 사용)
- query_engine.py : answer(q, lang) / asset_card(key, lang), 영문 질문 라우팅(TEMPLATES_EN), 영문 장비명 매칭
- app.py : /api/query, /api/asset_card 에 lang 전달
- 언어 선택은 브라우저에 저장, 팝아웃 창과 자동 동기화. `?lang=en` 으로 바로 영문 시작 가능

## 3. 함께 고친 기존 버그
- 장비 카드 추천질문이 다른 템플릿으로 빠지던 문제 (예: '약품공급 펌프 정지하면…' → 약품경로 답변,
  '중계펌프 MP-204A…' → 펌프장 답변) — 라우팅 순서 조정
- MP-204A 처럼 끝에 문자가 붙은 태그를 못 찾던 문제

## 검증
- 64개 장비 × 추천질문 3종 × 한/영 = 384건 라우팅 전수 확인, 시작화면 예시 질문 한/영 전수 확인
- 헤드리스 브라우저로 지도·관계도·설비동 상세·팝아웃·원시데이터 모달 한↔영 전환 확인 (JS 오류 0)
