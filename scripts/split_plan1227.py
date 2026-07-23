#!/usr/bin/env python3
"""국수처리장 및 관로1227.dxf → 계획평면도 13장 (C-094~C-106) 분할.
도곽 = 모델스페이스의 300×200 사각 13개 (EPSG:5186 실좌표 프레임).
시트번호 = 도곽 내부 높이 50 숫자 텍스트. C-{093+n} 명명 (C-094 = 계획평면도(1)).
사용: python scripts/split_plan1227.py 원본.dxf
"""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from dxf_to_svg import load_doc, render_window, entity_center_x, entity_ys

def main(path):
    doc = load_doc(Path(path))
    if doc is None: return
    msp = doc.modelspace()
    rects = []
    for e in msp.query("LWPOLYLINE"):
        try: pts = [(p[0], p[1]) for p in e.get_points()]
        except Exception: continue
        if not (4 <= len(pts) <= 5): continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        if abs(max(xs)-min(xs)-300) < 2 and abs(max(ys)-min(ys)-200) < 2:
            rects.append((min(xs), min(ys), max(xs), max(ys)))
    nums = []
    for e in msp.query("TEXT"):
        t = (e.dxf.text or "").strip()
        if re.fullmatch(r"1?\d", t) and getattr(e.dxf, "height", 0) >= 15:
            nums.append((int(t), e.dxf.insert.x, e.dxf.insert.y))
    print(f"도곽 {len(rects)}개, 번호 텍스트 {len(nums)}개")
    # 센터 사전계산 (13창 반복 계산 회피)
    # 거대 INSERT(전개 시 5,000+ 엔티티)는 통째 포함하면 SVG 폭발(C-103 274MB 사례)
    # → virtual_entities로 전개해 개별 엔티티를 캐시에 넣는다 (창 필터가 개별 적용됨)
    BIG_INSERT_THRESHOLD = 5000
    def expand(ins, out, depth=0):
        for v in ins.virtual_entities():
            if v.dxftype() == "INSERT" and depth < 6:
                expand(v, out, depth + 1); continue
            out.append(v)
    cache = []
    for e in msp:
        if e.dxftype() == "INSERT":
            n = sum(len(list(doc.blocks[b.dxf.name])) if b.dxftype() == "INSERT" else 1
                    for b in doc.blocks[e.dxf.name]) if e.dxf.name in doc.blocks else 0
            if n >= BIG_INSERT_THRESHOLD or e.dxf.name in ("A$C16496DF1",):
                sub = []; expand(e, sub)
                print(f"  [전개] 거대블록 {e.dxf.name} → {len(sub)}개 엔티티")
                for v in sub:
                    cx = entity_center_x(v)
                    if cx is None: continue
                    eys = entity_ys(v)
                    if not eys: continue
                    cache.append((v, cx, sum(eys) / len(eys)))
                continue
        cx = entity_center_x(e)
        if cx is None: continue
        eys = entity_ys(e)
        if not eys: continue
        cache.append((e, cx, sum(eys) / len(eys)))
    print(f"센터 캐시 {len(cache)}개")
    for x0, y0, x1, y1 in rects:
        inside = [n for n, x, y in nums if x0 <= x <= x1 and y0 <= y <= y1]
        if len(inside) != 1:
            print(f"  [경고] 창[{x0:,.0f},{y0:,.0f}] 번호 판정불가 {inside} — 건너뜀")
            continue
        sid = f"C-{93 + inside[0]:03d}"
        only = [int(a) for a in sys.argv[2:]]
        if only and inside[0] not in only: continue
        mx, my = 30, 20
        ents = [e for e, cx, cy in cache
                if x0 - mx <= cx <= x1 + mx and y0 - my <= cy <= y1 + my]
        render_window(doc, sid, x0, x1, y_win=(y0, y1),
                      pad_ratio=0.01, crs="EPSG:5186", pre_ents=ents)

if __name__ == "__main__":
    main(sys.argv[1])
