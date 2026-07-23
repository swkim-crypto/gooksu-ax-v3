#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AX 국수 하수처리 — 자연어→SPARQL 질의 엔진
대상: data/merged_guksu.ttl (4,020 트리플, rdflib 인메모리)

동작 방식:
 1) 템플릿 매칭 — 검증된 질의 유형(계통현황/소속계통/흐름체인/약품경로/도면/좌표/사양)
 2) 키워드 폴백 — 라벨 전문 검색
 3) LLM 폴백(선택) — ANTHROPIC_API_KEY 환경변수 있으면 질문→SPARQL 생성
"""
import os
import re
import json
from rdflib import Graph, Namespace
from pyproj import Transformer

AX = "http://samaneng.com/ax/onto#"
PREFIXES = """PREFIX ax: <http://samaneng.com/ax/onto#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
"""

SYSTEMS = {
    "SYS_PRETREAT": ["침사", "유량조정"],
    "SYS_BIO": ["생물반응조", "생물반응", "MBR", "공유조", "막분리"],
    "SYS_IPR": ["총인", "IPR", "ipr"],
    "SYS_DEWATER": ["슬러지", "탈수"],
    "SYS_DEODOR": ["탈취"],
    "SYS_UTILITY": ["용수"],
}


class GuksuEngine:
    def __init__(self, ttl_path="data/merged_guksu.ttl", extra_ttl=None):
        self.g = Graph()
        self.g.parse(ttl_path, format="turtle")
        for p in (extra_ttl or []):
            try:
                self.g.parse(p, format="turtle")
            except Exception as e:
                print(f"[warn] extra ttl 로드 실패 {p}: {e}")
        # 라벨 인덱스 (Asset 위주)
        self.assets = {}  # uri -> {label, tag}
        q = PREFIXES + """SELECT ?a ?l ?t WHERE {
            ?a a ax:Asset ; rdfs:label ?l . OPTIONAL { ?a ax:hasTag ?t } }"""
        for r in self.g.query(q):
            self.assets[str(r.a)] = {"label": str(r.l), "tag": str(r.t) if r.t else ""}
        # WKT(EPSG:5186) → WGS84 캐시
        self._tf = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
        self.coords = {}
        for r in self.g.query(PREFIXES + "SELECT ?s ?w WHERE { ?s geo:asWKT ?w }"):
            m = re.match(r"POINT\(([-\d.]+) ([-\d.]+)\)", str(r.w))
            if m:
                lon, lat = self._tf.transform(float(m.group(1)), float(m.group(2)))
                self.coords[str(r.s)] = [round(lon, 7), round(lat, 7)]

    def _edge_features(self, pairs):
        """[(uriA, labelA, uriB, labelB, edgeLabel)] → 지도 하이라이트 피처"""
        feats = []
        for ua, la, ub, lb, el in pairs:
            ca, cb = self.coords.get(ua), self.coords.get(ub)
            if ca:
                feats.append({"kind": "point", "coord": ca, "label": la})
            if cb:
                feats.append({"kind": "point", "coord": cb, "label": lb})
            if ca and cb:
                feats.append({"kind": "edge", "from": ca, "to": cb,
                              "label": el or f"{la}→{lb}"})
        # 중복 point 제거
        seen, out = set(), []
        for f in feats:
            k = (f["kind"], tuple(f.get("coord") or ()), f.get("label"), tuple(f.get("from") or ()))
            if k in seen: continue
            seen.add(k); out.append(f)
        return out

    # ---------- 공용 ----------
    def _run(self, sparql):
        return [
            {str(v): (str(row[v]) if row[v] is not None else None) for v in row.labels}
            for row in self.g.query(PREFIXES + sparql)
        ]

    def _find_system(self, text):
        for sid, kws in SYSTEMS.items():
            if any(k in text for k in kws):
                return sid
        return None

    def _find_asset(self, text):
        # 태그 직접 매칭 (M-502, DO-203 등)
        m = re.search(r"\b([A-Z]{1,3}-\d{3}(?:-\d)?)\b", text)
        if m:
            tag = m.group(1)
            for uri, a in self.assets.items():
                if a["tag"].startswith(tag) or tag in a["tag"]:
                    return uri, a
        # 라벨 부분 매칭 (긴 라벨 우선)
        cands = [(uri, a) for uri, a in self.assets.items() if a["label"] and a["label"] in text]
        if not cands:
            # 질문 안 명사가 라벨에 포함되는 역방향
            cands = [(uri, a) for uri, a in self.assets.items()
                     if len(a["label"]) >= 3 and any(tok in text for tok in [a["label"]])]
        if not cands:
            for uri, a in self.assets.items():
                core = re.sub(r"[\s()·]", "", a["label"])
                if core and core in re.sub(r"[\s()·]", "", text):
                    cands.append((uri, a))
        if cands:
            return max(cands, key=lambda c: len(c[1]["label"]))
        return None, None

    # ---------- 템플릿들 ----------
    def q_system_counts(self, _):
        sp = """SELECT ?sys ?label (COUNT(?a) AS ?n) WHERE {
            ?a ax:partOf ?sys . ?sys rdfs:label ?label }
            GROUP BY ?sys ?label ORDER BY DESC(?n)"""
        rows = self._run(sp)
        lines = [f"- {r['label']}: {r['n']}대" for r in rows]
        total = sum(int(r["n"]) for r in rows)
        return f"계통별 장비 현황 (총 {total}대):\n" + "\n".join(lines), rows, sp

    def q_asset_system(self, text):
        uri, a = self._find_asset(text)
        if not uri:
            return None
        sp = f"""SELECT ?sysLabel ?tag ?spec WHERE {{
            <{uri}> ax:partOf ?sys . ?sys rdfs:label ?sysLabel .
            OPTIONAL {{ <{uri}> ax:hasTag ?tag }} OPTIONAL {{ <{uri}> ax:spec ?spec }} }}"""
        rows = self._run(sp)
        if not rows:
            return f"'{a['label']}'의 소속 계통 정보가 그래프에 없습니다.", [], sp
        r = rows[0]
        ans = f"{a['label']}({r.get('tag') or a['tag']})은(는) **{r['sysLabel']}** 계통 소속입니다."
        if r.get("spec"):
            ans += f"\n사양: {r['spec']}"
        feats = ([{"kind": "point", "coord": self.coords[uri], "label": a["label"]}]
                 if uri in self.coords else [])
        return ans, rows, sp, feats

    def q_flow_chain(self, text):
        sid = self._find_system(text)
        filt = f"?a ax:partOf <http://samaneng.com/ax/data/guksu/system/{sid}> ." if sid else ""
        sp = f"""SELECT ?a ?b ?al ?bl ?m ?conf WHERE {{
            ?a ax:feeds ?b . ?a rdfs:label ?al . ?b rdfs:label ?bl .
            {filt}
            OPTIONAL {{ ?a ax:conveys ?m }} OPTIONAL {{ ?a ax:readConfidence ?conf }} }}"""
        rows = self._run(sp)
        if not rows:
            return None
        # 동일 엣지(high/med 중복) dedupe — high 우선
        best = {}
        for r in rows:
            k = (r["al"], r["bl"], r.get("m"))
            if k not in best or (r.get("conf") == "high" and best[k].get("conf") != "high"):
                best[k] = r
        rows = list(best.values())
        lines = []
        for r in rows:
            s = f"- {r['al']} → {r['bl']}"
            if r.get("m"):
                s += f" [{r['m']}]"
            if r.get("conf"):
                s += f" ({r['conf']})"
            lines.append(s)
        scope = dict((k, v[0]) for k, v in SYSTEMS.items()).get(sid, "전체")
        feats = self._edge_features([(r["a"], r["al"], r["b"], r["bl"], r.get("m")) for r in rows])
        return f"{scope} 흐름 관계 {len(rows)}건:\n" + "\n".join(lines), rows, sp, feats

    def q_chemical(self, _):
        sp = """SELECT ?a ?b ?al ?bl ?m WHERE {
            ?a ax:feeds ?b ; ax:conveys ?m . ?a rdfs:label ?al . ?b rdfs:label ?bl }"""
        rows = self._run(sp)
        lines = [f"- {r['m']}: {r['al']} → {r['bl']}" for r in rows]
        feats = self._edge_features([(r["a"], r["al"], r["b"], r["bl"], r["m"]) for r in rows])
        located = sum(1 for f in feats if f["kind"] == "edge")
        ans = f"약품/매체 주입 경로 {len(rows)}건:\n" + "\n".join(lines)
        if located:
            ans += f"\n\n(지도에 좌표 확보된 {located}개 경로를 표시했습니다)"
        return ans, rows, sp, feats

    def q_drawing(self, text):
        m = re.search(r"\b([A-Z]{1,2}P?-\d{3})\b", text)
        if not m:
            return None
        no = m.group(1)
        sp = f"""SELECT ?d ?title ?disc ?kind ?page ?docLabel WHERE {{
            ?d ax:drawingNo "{no}" . OPTIONAL {{ ?d rdfs:label ?title }}
            OPTIONAL {{ ?d ax:discipline ?disc }} OPTIONAL {{ ?d ax:drawingKind ?kind }}
            OPTIONAL {{ ?d ax:pdfPage ?page }}
            OPTIONAL {{ ?d ax:documents ?x . ?x rdfs:label ?docLabel }} }}"""
        rows = self._run(sp)
        if not rows:
            return f"도면 {no}이(가) 레지스트리에 없습니다.", [], sp
        r = rows[0]
        ans = f"도면 {no} — {r.get('title') or ''}\n분야 {r.get('disc')}, 성격 {r.get('kind')}, PDF p.{r.get('page')}"
        docs = [x["docLabel"] for x in rows if x.get("docLabel")]
        if docs:
            ans += "\n문서화 대상: " + ", ".join(sorted(set(docs)))
        return ans, rows, sp

    def q_coords(self, _):
        sp = """SELECT ?c (COUNT(?s) AS ?n) (SAMPLE(?l) AS ?ex) WHERE {
            ?s geo:asWKT ?w ; a ?c . OPTIONAL { ?s rdfs:label ?l } } GROUP BY ?c"""
        rows = self._run(sp)
        names = {AX + "Asset": "장비", AX + "Facility": "처리시설", AX + "Manhole": "맨홀", AX + "PipeStation": "관로측점"}
        lines = [f"- {names.get(r['c'], r['c'])}: {r['n']}개 (예: {r.get('ex')})" for r in rows]
        return "실좌표(EPSG:5186 WKT) 보유 객체:\n" + "\n".join(lines), rows, sp

    def q_spec(self, text):
        uri, a = self._find_asset(text)
        if not uri:
            return None
        sp = f"""SELECT ?tag ?spec ?qty ?kw ?sysLabel ?status WHERE {{
            OPTIONAL {{ <{uri}> ax:hasTag ?tag }} OPTIONAL {{ <{uri}> ax:spec ?spec }}
            OPTIONAL {{ <{uri}> ax:quantity ?qty }} OPTIONAL {{ <{uri}> ax:powerKW ?kw }}
            OPTIONAL {{ <{uri}> ax:partOf ?s . ?s rdfs:label ?sysLabel }}
            OPTIONAL {{ <{uri}> ax:tagStatus ?status }} }}"""
        rows = self._run(sp)
        if not rows:
            return None
        r = rows[0]
        parts = [f"{a['label']} ({r.get('tag')})"]
        if r.get("spec"):
            parts.append(f"사양: {r['spec']}")
        if r.get("qty"):
            parts.append(f"수량: {r['qty']}")
        if r.get("kw"):
            parts.append(f"동력: {r['kw']} kW")
        if r.get("sysLabel"):
            parts.append(f"계통: {r['sysLabel']}")
        if r.get("status"):
            parts.append(f"검증상태: {r['status']}")
        feats = ([{"kind": "point", "coord": self.coords[uri], "label": a["label"]}]
                 if uri in self.coords else [])
        return "\n".join(parts), rows, sp, feats

    # ---------- 물량/동력 템플릿 ----------
    def q_system_quantity(self, text):
        """계통별 배관 물량/중량 집계."""
        sid = self._find_system(text)
        filt = f"?q ax:partOf <http://samaneng.com/ax/data/guksu/system/{sid}> ." if sid else ""
        sp = f"""SELECT ?sl (COUNT(?q) AS ?n) (SUM(?t) AS ?len) (SUM(?w) AS ?wt) WHERE {{
            ?q a ax:QuantityItem ; ax:partOf ?s . ?s rdfs:label ?sl .
            {filt}
            OPTIONAL {{ ?q ax:qtyTotal ?t }} OPTIONAL {{ ?q ax:weight ?w }} }}
            GROUP BY ?sl ORDER BY DESC(?n)"""
        rows = self._run(sp)
        if not rows or all(int(r["n"]) == 0 for r in rows):
            return None
        lines = []
        for r in rows:
            wt = f", 중량 {float(r['wt']):.0f}kg" if r.get("wt") else ""
            ln = f", 연장 {float(r['len']):.0f}m" if r.get("len") else ""
            lines.append(f"- {r['sl']}: {r['n']}개 항목{ln}{wt}")
        head = f"{SYSTEMS.get(sid, ['전체'])[0] if sid else '계통별'} 배관 물량:"
        return head + "\n" + "\n".join(lines), rows, sp

    def q_asset_quantity(self, text):
        """장비 태그로 관련 배관 물량 (아이소시트 경유)."""
        uri, a = self._find_asset(text)
        if not uri:
            return None
        sp = f"""SELECT ?no ?title ?item ?spec ?tot ?unit WHERE {{
            ?iso ax:referencesAsset <{uri}> ; ax:sheetNo ?no .
            OPTIONAL {{ ?iso ax:sheetTitle ?title }}
            ?q ax:derivedFrom ?iso ; ax:itemName ?item ; ax:spec ?spec .
            OPTIONAL {{ ?q ax:qtyTotal ?tot }} OPTIONAL {{ ?q ax:unit ?unit }}
        }} ORDER BY ?no LIMIT 40"""
        rows = self._run(sp)
        if not rows:
            return f"'{a['label']}'({a['tag']})에 연결된 배관 물량이 없습니다. (배관 아이소에 주기되지 않은 장비일 수 있습니다)", [], sp
        sheets = sorted(set(r["no"] for r in rows))
        lines = [f"- {r['item']} {r['spec']}: {r.get('tot') or '?'} {r.get('unit') or ''}" for r in rows[:15]]
        ans = f"{a['label']}({a['tag']}) 관련 배관 물량 — 아이소시트 {', '.join(sheets)}:\n" + "\n".join(lines)
        if len(rows) > 15:
            ans += f"\n… 외 {len(rows)-15}건"
        feats = ([{"kind": "point", "coord": self.coords[uri], "label": a["label"]}]
                 if uri in self.coords else [])
        return ans, rows, sp, feats

    def q_pumpstation(self, text):
        """펌프장 펌프·전원 계통."""
        sp = """SELECT ?stl ?pl ?tag ?ml WHERE {
            ?p ax:poweredBy ?m ; ax:locatedIn ?st ; rdfs:label ?pl .
            OPTIONAL { ?p ax:hasTag ?tag }
            ?m rdfs:label ?ml . ?st rdfs:label ?stl } ORDER BY ?stl ?pl"""
        rows = self._run(sp)
        if not rows:
            return None
        byst = {}
        for r in rows:
            byst.setdefault(r["stl"], []).append(f"{r.get('tag') or r['pl']} ← {r['ml']}")
        lines = []
        for st, ps in byst.items():
            lines.append(f"[{st}]")
            lines += [f"  - {p}" for p in ps]
        return "중계펌프장 펌프·전원 계통:\n" + "\n".join(lines), rows, sp

    def q_downstream(self, text):
        """장비 고장/정지 시 하류 영향 범위 — feeds+ 경로 탐색."""
        uri, a = self._find_asset(text)
        if not uri:
            return None
        sp = f"""SELECT DISTINCT ?b ?bl ?sysl WHERE {{
            <{uri}> ax:feeds+ ?b . ?b rdfs:label ?bl .
            OPTIONAL {{ ?b ax:partOf ?s . ?s rdfs:label ?sysl }} }}"""
        rows = self._run(sp)
        if not rows:
            return (f"{a['label']}({a['tag']})의 하류(feeds) 객체가 그래프에 없습니다. "
                    f"흐름 체인의 말단이거나 계통도 미편입 구간일 수 있습니다."), [], sp
        lines = [f"- {r['bl']}" + (f" ({r['sysl']})" if r.get("sysl") else "") for r in rows]
        ans = (f"{a['label']}({a['tag']}) 정지 시 하류 영향 범위 — {len(rows)}개 객체:\n"
               + "\n".join(lines)
               + "\n\n※ 위상(feeds) 기준 도달 범위입니다. 우회 계열·예비기 여부는 별도 확인 필요.")
        pairs = [(uri, a["label"], r["b"], r["bl"], None) for r in rows]
        feats = self._edge_features(pairs)
        return ans, rows, sp, feats

    # ---------- 태그 종합 카드 (노드 클릭용) ----------
    def asset_card(self, key):
        """URI/태그/라벨 → 장비 종합 카드 JSON.
        기본정보 + 소속계통 + 직접 흐름(in/out) + 아이소시트 + 배관물량 합 + 좌표."""
        uri, a = (key, self.assets.get(key)) if key in self.assets else self._find_asset(key)
        if not uri:
            return None
        card = {"uri": uri, "label": a["label"], "tag": a["tag"]}
        r = self._run(f"""SELECT ?spec ?qty ?kw ?sysl ?status WHERE {{
            OPTIONAL {{ <{uri}> ax:spec ?spec }} OPTIONAL {{ <{uri}> ax:quantity ?qty }}
            OPTIONAL {{ <{uri}> ax:powerKW ?kw }} OPTIONAL {{ <{uri}> ax:tagStatus ?status }}
            OPTIONAL {{ <{uri}> ax:partOf ?s . ?s rdfs:label ?sysl }} }}""")
        if r:
            card.update({k: v for k, v in r[0].items() if v})
        card["feeds_out"] = self._run(f"""SELECT ?bl ?m WHERE {{
            <{uri}> ax:feeds ?b . ?b rdfs:label ?bl .
            OPTIONAL {{ <{uri}> ax:conveys ?m }} }}""")
        card["feeds_in"] = self._run(f"""SELECT ?al ?m WHERE {{
            ?x ax:feeds <{uri}> ; rdfs:label ?al .
            OPTIONAL {{ ?x ax:conveys ?m }} }}""")
        card["iso_sheets"] = self._run(f"""SELECT ?no ?title WHERE {{
            ?iso ax:referencesAsset <{uri}> ; ax:sheetNo ?no .
            OPTIONAL {{ ?iso ax:sheetTitle ?title }} }} ORDER BY ?no""")
        qsum = self._run(f"""SELECT (SUM(?t) AS ?len) (SUM(?w) AS ?wt) (COUNT(?q) AS ?n) WHERE {{
            ?iso ax:referencesAsset <{uri}> . ?q ax:derivedFrom ?iso .
            OPTIONAL {{ ?q ax:qtyTotal ?t }} OPTIONAL {{ ?q ax:weight ?w }} }}""")
        if qsum and qsum[0].get("n") and int(qsum[0]["n"]):
            card["pipe_summary"] = qsum[0]
        if uri in self.coords:
            card["coord"] = self.coords[uri]
        return card

    # ---------- 관계 시각화 데이터 ----------
    def graph_data(self):
        """공정 흐름도/계통 트리/물량 오버레이 공용 그래프 JSON."""
        SYS_LABEL = {}
        for r in self.g.query(PREFIXES + """SELECT ?s ?l WHERE {
            ?s rdfs:label ?l . FILTER(STRSTARTS(STR(?s), "http://samaneng.com/ax/data/guksu/system/")) }"""):
            SYS_LABEL[str(r.s)] = str(r.l)
        nodes, edges = {}, []

        # 계통 노드
        for su, sl in SYS_LABEL.items():
            nodes[su] = {"data": {"id": su, "label": sl, "kind": "system"}}
        # 장비 노드 + 계통 소속(트리 엣지)
        for r in self.g.query(PREFIXES + """SELECT ?a ?l ?s ?tag WHERE {
            ?a a ax:Asset ; rdfs:label ?l . OPTIONAL { ?a ax:partOf ?s }
            OPTIONAL { ?a ax:hasTag ?tag } }"""):
            au = str(r.a)
            nodes.setdefault(au, {"data": {
                "id": au, "label": str(r.l), "kind": "asset",
                "tag": str(r.tag) if r.tag else "",
                "system": str(r.s) if r.s else ""}})
            if r.s:
                edges.append({"data": {"id": f"part_{au}", "source": str(r.s),
                                       "target": au, "rel": "partOf"}})
        # 장비별 배관 물량 합 (오버레이용) — 아이소 경유
        qmap = {}
        for r in self.g.query(PREFIXES + """SELECT ?a (SUM(?t) AS ?tot) WHERE {
            ?iso ax:referencesAsset ?a . ?q ax:derivedFrom ?iso ;
            ax:qtyTotal ?t ; ax:itemName "파이프" } GROUP BY ?a"""):
            qmap[str(r.a)] = round(float(r.tot), 1)
        for au, q in qmap.items():
            if au in nodes:
                nodes[au]["data"]["pipeQty"] = q
        # feeds 엣지 (asset→asset, high 우선 dedupe) + 물량 얹기
        best = {}
        for r in self.g.query(PREFIXES + """SELECT ?a ?b ?m ?c WHERE {
            ?a ax:feeds ?b ; a ax:Asset . ?b a ax:Asset .
            OPTIONAL { ?a ax:conveys ?m } OPTIONAL { ?a ax:readConfidence ?c } }"""):
            a, b = str(r.a), str(r.b)
            k = (a, b)
            conf = str(r.c) if r.c else ""
            if k not in best or (conf == "high" and best[k]["conf"] != "high"):
                best[k] = {"conf": conf, "m": str(r.m) if r.m else ""}
        for (a, b), meta in best.items():
            w = qmap.get(a, 0)
            edges.append({"data": {
                "id": f"feed_{a}_{b}", "source": a, "target": b, "rel": "feeds",
                "conf": meta["conf"], "media": meta["m"], "pipeQty": w}})
        # 펌프장·MCC (전원 계통)
        for r in self.g.query(PREFIXES + """SELECT ?st ?stl WHERE {
            ?st a ax:PumpStation ; rdfs:label ?stl }"""):
            nodes[str(r.st)] = {"data": {"id": str(r.st), "label": str(r.stl), "kind": "pumpstation"}}
        for r in self.g.query(PREFIXES + """SELECT ?m ?ml ?st WHERE {
            ?m a ax:MCC ; rdfs:label ?ml ; ax:locatedIn ?st }"""):
            nodes[str(r.m)] = {"data": {"id": str(r.m), "label": str(r.ml), "kind": "mcc"}}
            edges.append({"data": {"id": f"in_{r.m}", "source": str(r.st),
                                   "target": str(r.m), "rel": "contains"}})
        for r in self.g.query(PREFIXES + """SELECT ?p ?m WHERE {
            ?p ax:poweredBy ?m }"""):
            if str(r.p) in nodes:
                edges.append({"data": {"id": f"pwr_{r.p}", "source": str(r.m),
                                       "target": str(r.p), "rel": "powers"}})
        return {"nodes": list(nodes.values()), "edges": edges,
                "systems": [{"id": k, "label": v} for k, v in SYS_LABEL.items()]}

    def q_keyword(self, text):
        toks = [t for t in re.split(r"[\s?？.,]+", text) if len(t) >= 2][:5]
        if not toks:
            return None
        filt = " || ".join(f'CONTAINS(?l, "{t}")' for t in toks)
        sp = f"""SELECT ?s ?l ?c WHERE {{ ?s rdfs:label ?l ; a ?c .
            FILTER({filt}) }} LIMIT 20"""
        rows = self._run(sp)
        if not rows:
            return None
        lines = [f"- {r['l']} ({r['c'].split('#')[-1]})" for r in rows]
        return f"관련 객체 {len(rows)}건:\n" + "\n".join(lines), rows, sp

    # ---------- 라우터 ----------
    TEMPLATES = [
        (r"펌프장|중계펌프|전원.*계통|MCC|어느 배전반", "q_pumpstation"),
        (r"(물량|중량|배관량|자재).*(계통|생물|침사|총인|용수|슬러지|탈취|전체)|계통.*(물량|중량)", "q_system_quantity"),
        (r"[A-Z]{1,2}P?-\d{3}.*(물량|배관|중량)|물량.*[A-Z]{1,2}P?-\d{3}", "q_asset_quantity"),
        (r"계통별|계통 현황|장비.*(몇|수|현황)", "q_system_counts"),
        (r"어느 계통|무슨 계통|소속", "q_asset_system"),
        (r"약품|주입", "q_chemical"),
        (r"하류|영향|고장|멈추|정지.*(영향|하류|범위)", "q_downstream"),
        (r"흐름|체인|경로|순서", "q_flow_chain"),
        (r"[A-Z]{1,2}P?-\d{3}.*(도면|문서|뭐|무엇|내용)|도면.*[A-Z]{1,2}P?-\d{3}", "q_drawing"),
        (r"좌표|위치.*(보유|객체)|실좌표", "q_coords"),
        (r"물량|중량|배관량", "q_system_quantity"),
        (r"사양|스펙|동력|용량|수량", "q_spec"),
    ]

    def answer(self, question):
        def pack(out, route):
            if len(out) == 4:
                ans, rows, sp, feats = out
            else:
                ans, rows, sp = out; feats = []
            d = {"answer": ans, "rows": rows, "sparql": sp, "route": route}
            if feats: d["map"] = {"features": feats}
            return d
        for pat, fn in self.TEMPLATES:
            if re.search(pat, question):
                out = getattr(self, fn)(question)
                if out:
                    return pack(out, fn)
        # 키워드 폴백
        out = self.q_keyword(question)
        if out:
            return pack(out, "keyword")
        # LLM 폴백
        llm = self.llm_fallback(question)
        if llm:
            return llm
        return {"answer": "해당 질문에 맞는 질의 템플릿을 찾지 못했습니다. 장비 태그(M-502 등)나 계통명(생물반응조 등)을 포함해 다시 질문해 주세요.",
                "rows": [], "sparql": None, "route": "none"}

    def llm_fallback(self, question):
        """ANTHROPIC_API_KEY 있으면 질문→SPARQL 생성 (없으면 None)"""
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        import urllib.request
        schema_hint = ("클래스: ax:Asset(장비, hasTag/spec/quantity/powerKW/partOf/tagStatus), "
                       "ax:Drawing(drawingNo/discipline/drawingKind/pdfPage/documents), "
                       "ax:Manhole, ax:PipeStation, ax:Facility(geo:asWKT), ax:Process. "
                       "관계: ax:feeds(흐름), ax:conveys(매체), ax:partOf(계통), ax:documents. "
                       "계통 URI: http://samaneng.com/ax/data/guksu/system/SYS_{PRETREAT|BIO|IPR|DEWATER|UTILITY|DEODOR}")
        body = json.dumps({
            "model": "claude-sonnet-4-6", "max_tokens": 1000,
            "messages": [{"role": "user", "content":
                f"다음 RDF 스키마에 대한 SPARQL SELECT 쿼리만 출력(설명·백틱 금지). 스키마: {schema_hint}\nPREFIX는 ax:/rdfs:/geo: 사용 가능.\n질문: {question}"}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"content-type": "application/json", "x-api-key": key,
                     "anthropic-version": "2023-06-01"})
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=30))
            sparql = resp["content"][0]["text"].strip()
            rows = self._run(sparql)
            lines = [", ".join(f"{k}={v}" for k, v in r.items()) for r in rows[:20]]
            return {"answer": f"LLM 생성 질의 결과 {len(rows)}건:\n" + "\n".join(lines),
                    "rows": rows, "sparql": sparql, "route": "llm"}
        except Exception as e:
            return {"answer": f"LLM 폴백 실패: {e}", "rows": [], "sparql": None, "route": "llm_error"}


if __name__ == "__main__":
    eng = GuksuEngine()
    tests = [
        "계통별 장비 수 알려줘",
        "슬러지탈수 흐름 체인 보여줘",
        "약품 주입 경로는?",
        "공기압축기는 어느 계통이야?",
        "M-009 도면은 무엇을 문서화해?",
        "실좌표 보유 객체는?",
        "협잡물종합처리기 사양 알려줘",
    ]
    for t in tests:
        r = eng.answer(t)
        print(f"\nQ: {t}  [route={r['route']}]")
        print(r["answer"])
