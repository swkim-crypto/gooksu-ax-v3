#!/usr/bin/env python3
"""DXF → SVG 변환 파이프라인 — 설비동 상세 뷰 도면 배경용.

단일 시트:
    python scripts/dxf_to_svg.py 파일.dxf
다중 시트 자동 분할 (한 모델스페이스에 여러 도면이 나란히 작도된 경우):
    python scripts/dxf_to_svg.py 파일.dxf --split "M-0\\d\\d"

분할 원리 (국수 M-006~011 / M-012~014에서 검증):
    1) 도면번호 텍스트(정규식)를 앵커로 수집 → 피치 = 인접 간격 중앙값
    2) 인접 앵커 사이 최대 공백 갭의 중앙 = 시트 경계 컷
    3) 컷-앵커 오프셋 중앙값으로 균일화 → 전 시트 창 확정
    4) 창별로 엔티티 필터 렌더 → static/drawings/{도면번호}.svg + .calib.json

calib.json: { "extents": [x0, y0, x1, y1] }  # 모델공간 로컬좌표 창
    배치도(M-012~014)의 extents는 abox_placement_localxy.ttl 시트 로컬좌표와
    동일 프레임이므로 마커 정합에 그대로 사용 가능.

주의: 위장 DWG(AC10* 헤더)·XREF 빈 껍데기는 자동 검출·건너뜀 (인수인계 v2 §2).
"""
import sys, json, re
from pathlib import Path
import numpy as np

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "drawings"


def entity_center_x(e):
    try:
        t = e.dxftype()
        if t == "LINE":
            return (e.dxf.start.x + e.dxf.end.x) / 2
        if t == "LWPOLYLINE":
            pts = e.get_points()
            return sum(p[0] for p in pts) / len(pts)
        if hasattr(e.dxf, "insert"):
            return e.dxf.insert.x
        if hasattr(e.dxf, "center"):
            return e.dxf.center.x
    except Exception:
        return None
    return None


def entity_ys(e):
    try:
        t = e.dxftype()
        if t == "LINE":
            return [e.dxf.start.y, e.dxf.end.y]
        if t == "LWPOLYLINE":
            return [p[1] for p in e.get_points()]
        if hasattr(e.dxf, "insert"):
            return [e.dxf.insert.y]
        if hasattr(e.dxf, "center"):
            return [e.dxf.center.y]
    except Exception:
        return []
    return []


def load_doc(dxf_path: Path):
    import ezdxf
    head = dxf_path.read_bytes()[:6]
    if head.startswith(b"AC10"):
        print(f"  [건너뜀] {dxf_path.name}: 바이너리 DWG 헤더 {head} → ODA로 DXF 재저장 필요")
        return None
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    real = [e for e in msp if e.dxftype() != "INSERT" or
            len(doc.blocks[e.dxf.name]) > 0]
    if len(real) < 20:
        print(f"  [건너뜀] {dxf_path.name}: 실체 {len(real)}개 — XREF 껍데기 의심")
        return None
    return doc


def find_windows(doc, pattern):
    """앵커 텍스트 → 시트 창 목록 [(sheet_id, x0, x1)]"""
    msp = doc.modelspace()
    pat = re.compile(pattern)
    anchors = []
    for e in msp.query("TEXT MTEXT"):
        t = (e.dxf.text if e.dxftype() == "TEXT" else e.text) or ""
        m = pat.search(t.replace(" ", ""))
        if m:
            anchors.append((e.dxf.insert.x, m.group()))
    if len(anchors) < 2:
        print(f"  [분할불가] 앵커 {len(anchors)}개 — 패턴/도면 확인 필요")
        return None
    anchors.sort()
    ax = [a[0] for a in anchors]
    pitch = float(np.median(np.diff(ax)))
    xs = np.sort(np.array([x for x in (entity_center_x(e) for e in msp) if x is not None]))
    # 인접 앵커 사이 최대 갭의 중앙 → 컷 후보 → 오프셋 균일화
    offs = []
    for a, b in zip(ax[:-1], ax[1:]):
        seg = xs[(xs > a) & (xs < b)]
        if len(seg) < 2:
            offs.append((a + b) / 2 - a); continue
        gaps = np.diff(seg)
        i = int(np.argmax(gaps))
        offs.append((seg[i] + seg[i + 1]) / 2 - a)
    off = float(np.median(offs))
    wins = []
    for x, sid in anchors:
        wins.append((sid, x + off - pitch, x + off))
    print(f"  앵커 {len(anchors)}개, 피치 {pitch:,.0f}, 컷오프셋 {off:,.0f}")
    return wins


def render_window(doc, sheet_id, x0, x1, y_win=None, pad_ratio=0.02, crs=None, pre_ents=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    msp = doc.modelspace()
    pad = (x1 - x0) * pad_ratio
    margin = (x1 - x0) * 0.10  # 경계 걸친 엔티티 포용
    ents, ys = [], []
    if pre_ents is not None:
        ents = pre_ents
        for e in ents:
            ys += entity_ys(e)
    for e in (msp if pre_ents is None else []):
        cx = entity_center_x(e)
        if cx is None or not (x0 - margin <= cx <= x1 + margin):
            continue
        if y_win:
            eys = entity_ys(e)
            if not eys: continue
            cy = sum(eys) / len(eys)
            ym = (y_win[1] - y_win[0]) * 0.10
            if not (y_win[0] - ym <= cy <= y_win[1] + ym): continue
        ents.append(e)
        ys += entity_ys(e)
    if not ents:
        print(f"  [{sheet_id}] 창 내 엔티티 없음 — 건너뜀"); return
    if y_win:
        y0, y1 = y_win
        ypad = (y1 - y0) * pad_ratio
    else:
        ya = np.array(ys)
        y0, y1 = np.percentile(ya, 0.2), np.percentile(ya, 99.8)
        ypad = (y1 - y0) * 0.03

    fig = plt.figure(figsize=(16, 16 * (y1 - y0 + 2 * ypad) / (x1 - x0 + 2 * pad)))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_entities(ents)
    backend.finalize()
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(x0 - pad, x1 + pad)
    ax.set_ylim(y0 - ypad, y1 + ypad)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg = OUT_DIR / f"{sheet_id}.svg"
    fig.savefig(svg, format="svg", bbox_inches="tight", pad_inches=0)
    fx0, fx1 = ax.get_xlim(); fy0, fy1 = ax.get_ylim()  # 최종 뷰포트 = calib
    plt.close(fig)
    (OUT_DIR / f"{sheet_id}.calib.json").write_text(json.dumps({
        "extents": [float(fx0), float(fy0), float(fx1), float(fy1)],
        "crs": crs or "sheet-local",
        "note": "crs=EPSG:5186이면 extents가 실좌표 → 마커 정합 즉시 가능.",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  [완료] {svg.name} ({svg.stat().st_size/1e6:.1f}MB) extents=[{x0-pad:,.0f},{y0-ypad:,.0f},{x1+pad:,.0f},{y1+ypad:,.0f}]")


def convert_single(doc, stem):
    from ezdxf import bbox
    msp = doc.modelspace()
    b = bbox.extents(msp, fast=True)
    if not b.has_data:
        print(f"  [{stem}] extents 계산 불가"); return
    render_window(doc, stem, b.extmin.x, b.extmax.x)


if __name__ == "__main__":
    split_pat = None
    skip = set()
    for i, a in enumerate(sys.argv):
        if a == "--split":
            split_pat = sys.argv[i + 1]
            skip.add(i); skip.add(i + 1)
    args = [a for i, a in enumerate(sys.argv) if i > 0 and i not in skip
            and not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(1)
    for p in args:
        path = Path(p)
        print(f"변환: {path.name}")
        doc = load_doc(path)
        if doc is None:
            continue
        if split_pat:
            wins = find_windows(doc, split_pat)
            if wins:
                for sid, x0, x1 in wins:
                    render_window(doc, sid, x0, x1)
        else:
            convert_single(doc, path.stem.replace("_", "-"))
