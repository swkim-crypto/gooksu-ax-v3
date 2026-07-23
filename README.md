# 국수 하수처리 GIS+AI (AX 프로젝트)

온톨로지 기반 설계정보 질의 + GIS/관계도 뷰어.
- `data/merged_guksu.ttl` (4,068) + `data/abox_quantities.ttl` (물량·동력, 5,006) = 로드 시 **9,074 트리플**
- 중앙 패널: **지도** 뷰(GIS) ↔ **관계도** 뷰(Cytoscape) 탭 전환
- 관계도 3모드: 공정 흐름도 / 계통 트리 / 흐름+물량(엣지 굵기=배관 연장)

## 로컬 실행
```
pip install -r requirements.txt
python app.py          # http://localhost:5000
```

## Render 배포 (깃-렌더)
1. 이 폴더를 GitHub 리포로 push
2. Render → New Web Service → 리포 연결 (render.yaml 자동 인식)
3. 환경변수(선택):
   - `KAKAO_JS_KEY` — 카카오맵 JavaScript 키. 넣으면 배경지도가 카카오로 전환.
     카카오 개발자콘솔에 `https://<서비스명>.onrender.com` 도메인 등록 필요.
   - `ANTHROPIC_API_KEY` — 템플릿 밖 질문을 LLM이 SPARQL로 변환 (김프로님 키).
   - 둘 다 없어도 OSM 배경 + 템플릿 질의로 완전 동작.

## 구조
```
app.py            Flask: UI 서빙 + /api/query, /api/sparql, /api/layers, /api/graph
query_engine.py   rdflib 로드(merged + abox_quantities), 자연어→SPARQL
                  (템플릿 10종 + 키워드 + LLM 폴백) + graph_data() 관계도 익스포트
data/merged_guksu.ttl       코어 그래프 (장비62·계통6·도면·좌표·feeds)
data/abox_quantities.ttl    물량·동력 (아이소38·물량454·라인35·펌프장2·펌프5·케이블5)
static/geojson/   pipes/manholes/pumpstations/facility/equipment (WGS84)
static/           index.html, app.js, style.css (지도+관계도 뷰)
```

## 검증된 질의
- 설계: 계통별 장비 수 / 슬러지탈수 흐름 / 약품 주입 경로 / {장비} 어느 계통 /
  M-009 도면 문서화 대상 / 실좌표 보유 객체 / {장비} 사양
- 물량·동력(신규): 계통별 배관 중량 / {계통} 물량 / {장비 태그} 배관 물량 /
  {펌프장} 전원계통

## 물량 온톨로지 (abox_quantities.ttl)
배관 수량산출서 DXF(아이소메트릭)의 SHEET NO.를 조인 키로, 엑셀 물량행을
아이소시트에 연결하고 시트가 참조하는 장비 태그로 코어 그래프에 정합.
- `ax:IsoSheet` (sheetNo·sheetTitle·referencesAsset·hasPipeLine)
- `ax:QuantityItem` (itemName·spec·unit·qtyNet/Margin/Total·weight·**derivedFrom**→IsoSheet)
- `ax:PipeLine` (nominalDia·fluidCode·fluidName·material) — 유체코드 9종(TW/SW/AA/ES/RS/OG/MW/PL/DRN)
- 펌프장 동력: `ax:PumpStation`/`ax:MCC`/`ax:PowerCable`, 관계 `ax:poweredBy`(펌프←MCC)

### 물량 대사(照合)로 검출된 불일치
- M-224(공기차단밸브): 아이소엔 있으나 장비공사 마스터 52엔 부재 → 밸브 별도계상 or 마스터 확인 대상
- 엑셀 32시트 ⊂ DXF 38시트: 차이 6장(101/201/301/401/501/601)은 계통별 집계·유출 페이지
- 펌프장 동력 엑셀: "동력설비 설치공사" 시트만 사업명 정품(국수), 인입·TRAY·집계표 시트는
  "파주시 재이용" 템플릿 잔재 → 사업명 필터로 제외 (G0 파일건전성 게이트 실사례)

## 데이터 검역 이력
- 2026-07-16 (2차 보정·확정): 실건물(지번 983-30) 관리동 좌하단 실측 클릭
  (37.510586,127.391759) 기준으로 잔여 이동 (+206.1,+50.4)m 적용. DGS-B 측점
  기반 독립 예측(+219,+42)과 교차 일치. 근본 원인: 관로 CAD 내부에 프레임 혼재
  — 마을 관망·DGS 측점 블록은 참좌표, 부지경계·인접 신설관로 폴리라인은 약
  212m 서남서로 어긋난 프레임(강에 빠진 관로 33건과 동일 계열 이슈).
  C-002 최종 변환: 회전 57.541° + 부지정합 이동 + (206.1,50.4).
- 2026-07-16: C-002 프레임 보정 — 진위치 부지경계(New_block.dxf, 12각형)와 꼭지점
  정합으로 회전 57.541° + 평행이동 확정(잔차 0.000m). 시설·장비 GeoJSON 및
  TTL WKT 51건 변환. 장비 48종 전량 부지경계 내부 확인. C-002는 도곽 정렬을
  위해 57.5° 회전 작도된 도면이었음(수치지도 XREF 포함 전체가 회전 프레임).
- 2026-07-16: 처리시설 레이어를 C-002 원본 DXF에서 재구축(폴리곤51+선285+시설명21).
  기존 SHP판은 주석·범례 심볼이 실좌표에 섞여 축척 왜곡처럼 보이는 문제 → 폐기.
  부지는 공원 복개형(육상트랙·족구장) 지하화 시설로 확인 — 위성사진과 다르게 보이는 이유.
- 2026-07-16: 남한강 위에 표시되던 관로18·맨홀15건을 `*_quarantine.geojson`으로 분리.
  블록 SB003/013/018/105(본망에 부재), SB109 일부. 원본 DXF에서 좌표 이탈된
  잔재로 추정 — `국수처리장_및_관로1227.dxf` 원본 재확인 시 진위 판정 필요.
  merged_guksu.ttl에는 영향 없음(검역구역 WKT 0건).

## 데이터 갱신
merged_guksu.ttl 교체 후 재배포. GeoJSON은 shp_to_geojson.py(별도 산출물)로 재생성.
