# -*- coding: utf-8 -*-
"""원시데이터 폴더·파일명 영문 사전 생성 → static/rawdata/names_en.json
   용어 치환(최장일치) + 완전일치 예외(EXACT)."""
import json, re, sys

T = {
 # 지명·기관
 "양평군": "Yangpyeong-gun", "양평": "Yangpyeong", "국수": "Guksu", "도곡": "Dogok", "양동": "Yangdong",
 "용문": "Yongmun", "조달청": "PPS", "삼성": "Samsung",
 # 업체 (견적서)
 "에이시텍": "ACtech", "제이에스일렉트릭": "JS Electric", "케이엔지니어링": "K Engineering",
 "동성계전": "Dongsung Electric", "반석전기": "Bansuk Electric", "정안기술": "Jungan Tech",
 "정엔지니어링": "Jung Engineering", "파인텍": "Finetek", "천열에너지": "Cheonyeol Energy",
 "엘이디코람": "LED Koram", "엘이디파워": "LED Power", "UBY울산병영용사촌": "UBY Ulsan",
 "세네카": "Seneca", "A사": "Vendor A", "B사": "Vendor B", "C사": "Vendor C", "(주)": "",
 # 문서 구조
 "대간지": "Main Divider", "소간지": "Section Divider", "중간지": "Divider", "간지": "Divider",
 "표지": "Cover", "목차": "Contents", "세네카": "Spine", "도면목록표": "Drawing List", "도면목록": "Drawing List",
 "도면목차": "Drawing Index", "붙임": "Attachment", "첨부": "Attachment", "별첨": "Appendix",
 "보고서": "Report", "부록": "Appendix", "시방서": "Specifications", "도면": "Drawings",
 "산출서": "Calculations", "계산서": "Calculation", "수량산출서": "Quantity Takeoff", "수량산출내역": "Quantity Takeoff",
 "수량산출": "Quantity Takeoff", "수량": "Quantities", "내역": "Bill", "단가산출서": "Unit Price Analysis",
 "단가표": "Unit Price Table", "단가": "Unit Price", "견적서": "Quotation", "비교견적": "Comparative Quote",
 "견적": "Quote", "최종취합": "Final Compilation", "예산서": "Budget", "설계예산서": "Design Budget",
 "원가심사결과": "Cost Review Result", "원가계산서": "Cost Statement", "실내역": "Detailed Bill",
 "관급자재": "Owner-supplied Materials", "직접구매대상 검토": "Direct Purchase Review",
 "설계설명서": "Design Description", "편집": "edited", "최종": "final", "완": "final", "수정": "rev", "제출": "submitted",
 "반영": "applied", "서식": "form", "보완사항": "Supplementary Items", "보완의견": "Review Comments",
 "보완 요청": "Revision Request", "조치결과보고서": "Action Report", "조치결과서": "Action Report",
 "조치계획서": "Action Plan", "조치결과": "Action Result", "의견서": "Opinion", "의결서": "Resolution",
 "심의결과": "Review Result", "심의": "Review", "알림": "Notice", "승인공문": "Approval Letter", "승인": "Approval",
 "의견": "Opinion", "보고": "Report", "공증": "Notarized", "성능보증서": "Performance Guarantee",
 "결과보고서": "Result Report", "제60회": "60th",
 # 사업·재원
 "재원협의": "Funding Consultation", "총사업비 변경": "Total Project Cost Change", "총사업비": "Total Project Cost",
 "신·증설사업": "New/Expansion Project", "신？증설": "New/Expansion", "신,증설": "New/Expansion",
 "증설사업": "Expansion Project", "설치사업": "Installation Project", "설치공사": "Construction",
 "사업": "Project", "공법선정": "Process Selection", "기본설계자문": "Basic Design Advisory",
 "설계의 경제성 검토": "Value Engineering", "건설기술심의": "Construction Technology Review",
 "3개소": "3 Sites",
 # 시설
 "공공하수처리시설": "Public WWTP", "하수처리시설": "WWTP", "국수하수처리장": "Guksu WWTP",
 "하수처리장": "WWTP", "국수처리장": "Guksu Plant", "국수처리시설": "Guksu Plant", "처리시설": "Treatment Plant",
 "중계펌프장": "Relay Pump Station", "기존중계펌프장": "Existing Relay Pump Station", "중계펌프": "Relay Pump",
 "관리동": "Admin Bldg", "설비동": "Equipment Bldg", "전기실": "Electrical Room", "중앙제어실": "Central Control Room",
 "반응조": "Reactor", "밸브실": "Valve Chamber", "화장실": "Restroom",
 # 분야
 "토목, 건축, 기계, 조경": "Civil, Architecture, Mechanical, Landscape",
 "토목,건축,기계,조경": "Civil, Arch, Mech, Landscape", "토목건축기계조경": "Civil-Arch-Mech-Landscape",
 "토건기조": "Civil-Arch-Mech-Landscape", "전기 및 계측제어": "Electrical & Instrumentation",
 "건축기계설비": "Building Mechanical", "건축기계": "Building Mechanical", "건축설비": "Building Services",
 "건축전기": "Building Electrical", "건축구조": "Architectural Structure", "건축,구조": "Architecture, Structure",
 "소방기계": "Fire Mechanical", "소방전기": "Fire Electrical", "소방설비": "Fire Protection", "소방": "Fire Protection",
 "계측제어설비": "I&C Equipment", "계측제어": "I&C", "계측": "Instrumentation", "토목구조": "Civil Structure",
 "토목": "Civil", "건축": "Architecture", "기계": "Mechanical", "조경": "Landscape", "전기": "Electrical",
 "구조": "Structural", "분야": "", "공사": "Works", "설비공사": "Equipment Works", "건축공사": "Building Works",
 "조경공사": "Landscape Works", "토목공사": "Civil Works", "설비": "Equipment",
 # 도면 종류
 "전체계획평면도": "Overall Plan", "시설계획평면도": "Facility Plan", "계획평면도": "Plan View",
 "토공계획평면도종단,횡단면도": "Earthwork Plan & Sections", "구내배관종평면도": "Site Piping Plan & Profile",
 "종평면도": "Plan & Profile", "종평": "Plan & Profile", "횡단면도": "Cross Section", "횡단": "Cross Section",
 "압송종평": "Force Main Profile", "수리종단도": "Hydraulic Profile", "처리계통도": "Process Flow Diagram",
 "처리시설일반도": "Plant General Drawing", "배근도": "Rebar Drawing", "일반도": "General Drawing",
 "위치도": "Location Map", "색인도": "Key Map", "평면도": "Plan", "단면도": "Section", "입면도": "Elevation",
 "주단면도": "Main Section", "부분단면도": "Partial Section", "상세도": "Detail", "잡상세도": "Misc. Details",
 "각종상세도": "Misc. Details", "일람표": "Schedule", "계통도": "Diagram", "구성도": "Configuration",
 "단선결선도": "Single-line Diagram", "결선도": "Wiring Diagram", "배치도": "Layout", "기기배치": "Equipment Layout",
 "기계배치도": "Mechanical Layout", "건축배치도": "Site Layout", "건축개요": "Architectural Summary",
 "면적산출표": "Area Table", "주심도": "Grid Plan", "구조일반사항": "Structural General Notes",
 "구조평면도": "Structural Plan", "구조일람표": "Structural Schedule", "구조입면도": "Structural Elevation",
 "구조단면도": "Structural Section", "확대평면": "Enlarged Plan", "전개도": "Interior Elevation",
 "범례 및 주기사항": "Legend & Notes", "범례": "Legend", "일반사항 및 주의사항": "General Notes",
 "기기목록": "Equipment List", "도각": "Title Block", "물량산출도각": "Quantity Title Block",
 "실내재료마감표 및 마감상세도": "Interior Finish Schedule & Details", "방수계획도": "Waterproofing Plan",
 "단열계획도": "Insulation Plan", "토공계획도": "Earthwork Plan", "창호평면도 및 일람표": "Window/Door Plan & Schedule",
 "보강블럭상세도": "Reinforced Block Detail", "소화배관평면도": "Fire Piping Plan", "소화평면도": "Fire Protection Plan",
 "조경녹지구적도": "Green Area Plan", "조경식재계획도": "Planting Plan", "조경시설 및 포장계획도": "Landscape Facilities & Paving Plan",
 "포장단면 상세도": "Paving Section Detail", "식재부대 상세도": "Planting Detail", "등의자": "Bench",
 "파고라": "Pergola", "체력단련시설": "Fitness Equipment", "교통처리계획도": "Traffic Management Plan",
 "시공순서도": "Construction Sequence", "시공": "Construction",
 # 관로·토목 항목
 "오수관로": "Sewer", "오수관거": "Sewer", "오수간선관로": "Trunk Sewer", "오수압송관로": "Sewer Force Main",
 "오수받이": "Sewer Inlet", "우수관로": "Storm Sewer", "방류관로": "Outfall", "관로가시설": "Pipeline Temporary Works",
 "관로구간 가시설도": "Pipeline Temporary Works", "관로시설": "Pipeline", "관로": "Pipeline", "관거검사": "Sewer Inspection",
 "관거": "Sewer", "관부설공": "Pipe Laying", "구내배관공": "Site Piping", "구내배관": "Site Piping",
 "구체배관공": "Structure Piping", "시상수공": "Water Supply", "시상수": "Water Supply", "포장공": "Paving",
 "포장깨기 및 복구": "Pavement Removal & Restoration", "구내포장상세도": "Site Paving Detail", "포장": "Paving",
 "부대공": "Ancillary Works", "가시설공": "Temporary Works", "가시설": "Temporary Works", "토공": "Earthwork",
 "구조물공": "Structures", "단위수량": "Unit Quantities", "주요자재집계표": "Main Materials Summary",
 "주요자재 집계표": "Main Materials Summary", "총괄": "Summary", "품질시험": "Quality Testing",
 "제수변보통": "Gate Valve Box", "제수변키보호통상세도": "Valve Key Box Detail", "제수밸브": "Gate Valve",
 "이토, 공기,": "Drain, Air,", "돌망태": "Gabion", "세륜기": "Wheel Washer", "세륜세차시설": "Wheel Wash Facility",
 "관지수판": "Pipe Water Stop", "암룰철판": "Arm-roll Steel Plate", "보호철판": "Protective Steel Plate",
 "관매달기": "Pipe Hanging", "지장물 매달기": "Utility Hanging", "기존관로 연결": "Existing Pipe Connection",
 "격점": "Junction", "개량": "Upgrade", "터파기상세도": "Excavation Detail", "조립식PC맨홀": "Precast Manhole",
 "PC맨홀": "PC Manhole", "맨홀뚜껑": "Manhole Cover", "맨홀": "Manhole", "닥타일주철관": "Ductile Iron Pipe",
 "이중벽관": "Double-wall Pipe", "흄관": "Hume Pipe", "이형관보호공상세도": "Fitting Protection Detail",
 "카스토퍼상세도": "Car Stopper Detail", "공사용 안전시설": "Construction Safety Facilities",
 "공사용 진입도로": "Construction Access Road", "플랩밸브": "Flap Valve", "날개벽": "Wing Wall",
 "내충격": "Impact-resistant", "점검구": "Inspection Port", "메쉬휀스상세도": "Mesh Fence Detail",
 "출입문상세도": "Gate Detail", "출입문": "Entrance Door", "방진망": "Dust Screen", "시스템동바리": "System Shoring",
 "비점오염저감시설": "Non-point Pollution Facility", "부단수 할정자관": "Hot-tap Split Tee", "관자재": "Pipe Materials",
 "레미콘": "Ready-mix Concrete", "기계기초 및 슬리브": "Equipment Foundation & Sleeve",
 "임시비탈면 사면 안전성": "Temporary Slope Stability", "임시비탈면 지하수 발생량": "Temporary Slope Groundwater Inflow",
 "기초 지지력": "Foundation Bearing Capacity", "측량계산서": "Survey Calculation", "측량조사": "Survey",
 "측량 및 토질조사": "Survey & Soil Investigation", "토질조사": "Soil Investigation", "지반조사보고서": "Geotechnical Report",
 "지반계산서": "Geotechnical Calculation", "주상도": "Boring Log", "사진첩": "Photo Album", "실내시험": "Lab Tests",
 "현장투수시험": "Field Permeability Test", "수리계산서": "Hydraulic Calculation", "수리계산": "Hydraulic Calculation",
 "용량계산서": "Capacity Calculation", "용량계산": "Capacity Calculation", "계획지표 설정": "Planning Indicators",
 "계획지표": "Planning Indicators", "구조계산서": "Structural Calculation", "가시설구조계산서": "Temporary Works Structural Calc",
 "기계 하중 표시": "Mechanical Load Plan", "구조계산용": "for structural calc.", "기계하중수정": "mech. load revised",
 "건축 및 기계 하중": "Building & Mechanical Loads", "설비동 반력": "Equipment Bldg Reactions", "반력": "Reactions",
 "전산자료": "Computer Files", "본체구조해석": "Main Structure Analysis", "기둥P-M상관해석": "Column P-M Interaction",
 "기둥": "Column", "내측": "inner", "상시": "normal", "지진시": "seismic", "물질수지및": "Mass Balance & ",
 "설계농도": "design load", "저온": "low temp", "고농도": "high load", "저농도": "low load", "계열": " trains",
 "톤": " t",
 # 산출 항목
 "총괄분석표": "Summary Analysis", "분석표": "Analysis Table", "부재별집계표": "Summary by Member",
 "층별총집계표": "Summary by Floor", "층-부재별집계표": "Floor-Member Summary", "부재-층별집계표": "Member-Floor Summary",
 "부재별산출서": "Takeoff by Member", "공종별집계표": "Summary by Trade", "가설산출서": "Temporary Works Takeoff",
 "토공산출서": "Earthwork Takeoff", "공용산출서": "Common Areas Takeoff", "내부산출서": "Interior Takeoff",
 "조적산출서": "Masonry Takeoff", "외부산출서": "Exterior Takeoff", "동별창호리스트": "Window List by Bldg",
 "창호산출서": "Window/Door Takeoff", "구조산출서": "Structural Takeoff", "마감산출서": "Finishes Takeoff",
 "산출집계": "Takeoff Summary", "노임근거": "Labor Basis", "목록별산출서": "Takeoff by Item", "일반": "general",
 "배관물량산출서": "Piping Quantity Takeoff", "복합탈취기": "Combined Deodorizer", "탈취기 명칭변경": "deodorizer renamed",
 # 시방 장
 "총칙": "General", "토공사": "Earthworks", "콘크리트공사": "Concrete Works", "포장공사": "Paving Works",
 "관거공사": "Sewer Works", "방수공사": "Waterproofing", "가시설 공사": "Temporary Works", "기타공사": "Other Works",
 "자재구입및제작": "Material Procurement & Fabrication", "가설공사": "Temporary Works", "지정 및 기초공사": "Piling & Foundation",
 "조적공사": "Masonry", "석공사": "Stone Works", "타일공사": "Tile Works", "방수 및 방습공사": "Waterproofing & Dampproofing",
 "금속공사": "Metal Works", "외벽공사": "Exterior Wall Works", "미장공사": "Plastering", "유리 및 창호공사": "Glazing & Windows",
 "도장공사": "Painting", "수장공사": "Interior Finishes", "단열 및 내방화공사": "Insulation & Fireproofing",
 "알미늄시트판넬공사": "Aluminum Sheet Panel", "알미늄창호공사": "Aluminum Windows", "전기계측제어시방서": "E&I Specifications",
 "총설": "Overview", "일반현황 및 관련계획": "General Conditions & Related Plans", "현지조사": "Site Investigation",
 "기본계획": "Master Plan", "기본설계": "Basic Design", "실시설계": "Detailed Design", "유지관리계획": "O&M Plan",
 "재정계획": "Financial Plan",
 # 전기
 "전기용량계산서": "Electrical Capacity Calculation", "전기계산용량서": "Electrical Capacity Calculation",
 "전기계산서": "Electrical Calculation", "건축전기 계산서": "Building Electrical Calculation",
 "분전반 부하계산서": "Panelboard Load Calculation", "분전반": "Panelboard", "접지": "Grounding",
 "부하 및 장비용량계산서": "Load & Equipment Capacity Calculation", "소화펌프계산서": "Fire Pump Calculation",
 "기계용량계산서": "Mechanical Capacity Calculation", "감시제어": "SCADA", "IO리스트": "IO List",
 "전력인입간선": "Power Service Feeder", "동력설비": "Power Equipment", "접지설비": "Grounding System",
 "옥외 전력 및 통신간선설비": "Outdoor Power & Comms Feeders", "수변전설비": "Substation", "전동기 제어반": "Motor Control Panel",
 "현장조작반": "Local Control Panel", "기기배치 평면도": "Equipment Layout Plan", "접지 및 피뢰설비": "Grounding & Lightning Protection",
 "피뢰설비": "Lightning Protection", "옥외조명 및 방송설비": "Outdoor Lighting & PA", "조명기구": "Luminaire",
 "전등,전열설비": "Lighting & Receptacles", "전등 및 전열설비": "Lighting & Receptacles", "전등설비": "Lighting",
 "전열설비": "Receptacles", "통신설비": "Communications", "방송설비": "PA System", "설치 상세도": "Installation Detail",
 "중앙감시반": "Central Monitoring Panel", "계측기기": "Instruments", "수배전반": "Switchgear", "배전반": "Switchboard",
 "제조": "Manufacturing", "제작": "Fabrication", "전광방송": "LED Display & PA", "전등": "Lighting", "수질": "Water Quality",
 "공공하수처리시설 감시제어설비": "WWTP SCADA", "시스템구성도": "System Configuration", "전자유량계": "Electromagnetic Flowmeter",
 "냉난방,공기순환기": "HVAC & Air Circulator", "공기순환기": "Air Circulator", "전기바닥난방": "Electric Floor Heating",
 # 기계
 "탈취배관": "Odor Control Ducting", "배관지지대": "Pipe Support", "지지대": "Support", "기계도면": "Mechanical Drawings",
 "기계시방서": "Mechanical Specifications", "조경시방서": "Landscape Specifications",
 # 잡
 "하중": "Loads", "용량": "Capacity", "및": "&", "각종": "Misc.", "기존": "Existing", "전체": "Overall",
 "구내": "Site", "설치": "Installation", "검토": "Review", "결과": "Result",
 "자재": "Materials", "하수관로": "Sewer Network", "공통상세도": "Common Details", "10년": "10-yr",
 "탈취배관용": "for odor ducting ", "계획 평면도": "Plan", "전체계평": "Overall Plan", "계평": "Plan",
}

EXACT = {
 "0.최종(양평국수)": "0.Final (Yangpyeong Guksu)",
 "1. 토목, 건축, 기계, 조경": "1. Civil, Architecture, Mechanical, Landscape",
 "2. 전기 및 계측제어": "2. Electrical & Instrumentation",
 "3. 소방": "3. Fire Protection",
 "6 수량산출서": "6 Quantity Takeoff",
 "3. 내역 및 단가산출서": "3. Bill of Quantities & Unit Prices",
 "4. 설계의 경제성 검토(VE)": "4. Value Engineering (VE)",
 "1. 양평군 국수, 양동, 용문 신？증설 총사업비 변경 승인 및 재원협의 의견 알림(보고).hwp":
   "1. Yangpyeong Guksu-Yangdong-Yongmun New_Expansion — Total Cost Change Approval & Funding Opinion (report).hwp",
 "1. 양평군 국수·용문·양동 공공하수처리시설 신·증설사업 재원협의 보완 요청.hwp":
   "1. Yangpyeong Guksu-Yongmun-Yangdong WWTP Projects — Funding Consultation Revision Request.hwp",
 "국수 등 3개소 공공하수처리시설(신,증설)사업 공법선정 알림.hwp": "Guksu & 2 other WWTPs (new_expansion) — Process Selection Notice.hwp",
 "01. 국수처리시설_기본설계자문 조치계획서.pdf": "01. Guksu Plant — Basic Design Advisory Action Plan.pdf",
 "제9장 토질조사.zip": "Ch.9 Soil Investigation.zip",
 "04.조경.zip": "04.Landscape.zip",
 "양평마크.jpg": "Yangpyeong logo.jpg",
 "위치도.jpg": "Location map.jpg",
 "기계mpl.txt": "Mechanical mpl.txt", "소방전기mpl.txt": "Fire Electrical mpl.txt", "토목-하수관로분야mpl.txt": "Civil-Sewer mpl.txt",
 "xref위치도.dwg": "xref Location Map.dwg",
 "1.0 총괄 주요자재 집계표.xlsx": "1.0 Overall Main Materials Summary.xlsx",
}

HANGUL = re.compile(r"[가-힣]")
KEYS = sorted(T, key=len, reverse=True)

def tr(name):
    if name in EXACT:
        return EXACT[name]
    stem, ext = (name.rsplit(".", 1) + [""])[:2] if re.search(r"\.[A-Za-z0-9]{2,5}$", name) else (name, "")
    s = re.sub(r"제\s*0?(\d+)\s*장", r"Ch.\1 ", stem)          # 제01장 → Ch.1
    s = re.sub(r"\((\d)차\)", lambda m: f"({m.group(1)}{'st' if m.group(1)=='1' else 'nd' if m.group(1)=='2' else 'th'})", s)
    s = re.sub(r"(?<=\d)장", "", s)                                 # -1장 → -1
    for k in KEYS:
        if k in s:
            s = s.replace(k, f" {T[k]} ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\(\s+", "(", s); s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r"\s+([,_])", r"\1", s); s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"(\d)\.\s+", r"\1. ", s)
    s = re.sub(r"_\s+", "_", s); s = re.sub(r"\s+\.", ".", s); s = re.sub(r"\[\s+", "[", s)
    s = s.replace("()", "").strip(" -_")
    return s + ("." + ext if ext else "")

if __name__ == "__main__":
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    names = set()
    def w(n):
        names.add(n["name"]); [w(c) for c in n.get("children", [])]
    w(d["tree"])
    out = {n: tr(n) for n in sorted(names) if HANGUL.search(n)}
    left = {k: v for k, v in out.items() if HANGUL.search(v)}
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(out), "names;", len(left), "still contain Hangul")
    for k, v in left.items(): print("  !", k, "→", v)
