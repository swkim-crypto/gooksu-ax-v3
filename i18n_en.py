# -*- coding: utf-8 -*-
"""한→영 데이터 값 번역 (static/i18n/en.json 공용 사전 — 프론트 i18n.js와 같은 규칙)
 L(s): ① 완전일치 ② 공백 무시 일치 ③ 부분치환(최장일치) ④ 없으면 원문"""
import json
import os
import re

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "i18n", "en.json")
try:
    _D = json.load(open(_PATH, encoding="utf-8"))
except Exception as e:  # 사전이 없어도 앱은 동작 (한글 그대로)
    print(f"[warn] i18n 사전 로드 실패: {e}")
    _D = {"labels": {}, "terms": {}}

LABELS = _D.get("labels", {})
_NOSPACE = {re.sub(r"\s+", "", k): v for k, v in LABELS.items()}
_TERMS = sorted(_D.get("terms", {}).items(), key=lambda kv: -len(kv[0]))
_HANGUL = re.compile(r"[가-힣]")


def L(s):
    """데이터 값 하나를 영문으로. 한글이 없으면 그대로."""
    if s is None:
        return s
    s = str(s)
    if s in LABELS:
        return LABELS[s]
    if not _HANGUL.search(s):
        return s
    ns = re.sub(r"\s+", "", s)
    if ns in _NOSPACE:
        return _NOSPACE[ns]
    out = s
    for k, v in _TERMS:
        if k in out:
            out = out.replace(k, f" {v} ")
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"\s+([),])", r"\1", out)
    return out.strip()


def EN_TO_URI_INDEX(assets):
    """{uri: {label}} → [(en_label_lower, uri)] 긴 라벨 우선 (영문 질문의 장비 찾기용)"""
    idx = [(L(a["label"]).lower(), uri) for uri, a in assets.items() if a.get("label")]
    return sorted(idx, key=lambda t: -len(t[0]))
