#!/usr/bin/env python3
"""
원시데이터 폴더 → manifest.json (파일 '목록'만, 내용은 읽지 않음)
Raw-data folder -> manifest.json (file LISTING only; contents are never read)

사용법 / Usage (내 PC에서 1회 실행):
    python make_rawdata_manifest.py "D:/국수_원시자료" -o manifest.json
    python make_rawdata_manifest.py "D:/국수_원시자료" -o manifest.json --max-files 300 --hide "개인|연락처"

출력된 manifest.json을 앱의 static/rawdata/manifest.json 위치에 두면 됩니다.
"""
import argparse, json, os, re, sys, time
from collections import Counter

def human(n):
    """윈도우 속성창과 같은 표기 (1024 단위, 소수 둘째 자리 버림 → 1.85GB)"""
    import math
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.0f}{u}" if u == "B" else f"{math.floor(n * 100) / 100:.2f}{u}"
        n /= 1024
    return f"{n:.2f}PB"

def walk(root, max_files, hide_re):
    """디렉터리를 트리(dict)로 변환. 폴더별 파일은 max_files개까지만 기록, 나머지는 개수만."""
    def node_for(path, name):
        node = {"name": name, "type": "dir", "size": 0, "files": 0, "children": []}
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            node["error"] = "permission"
            return node
        file_nodes, omitted = [], 0
        for e in entries:
            if hide_re and hide_re.search(e.name):
                continue
            if e.is_dir(follow_symlinks=False):
                child = node_for(e.path, e.name)
                node["children"].append(child)
                node["size"] += child["size"]
                node["files"] += child["files"]
            elif e.is_file(follow_symlinks=False):
                st = e.stat()
                node["size"] += st.st_size
                node["files"] += 1
                ext = os.path.splitext(e.name)[1].lower().lstrip(".") or "(none)"
                EXT[ext] += 1
                EXT_SIZE[ext] += st.st_size
                if len(file_nodes) < max_files:
                    file_nodes.append({
                        "name": e.name, "type": "file", "ext": ext, "size": st.st_size,
                        "mtime": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)),
                    })
                else:
                    omitted += 1
        node["children"].extend(file_nodes)
        if omitted:
            node["omitted"] = omitted
        return node
    return node_for(root, os.path.basename(os.path.abspath(root)) or root)

def count_dirs(n):
    return sum(1 + count_dirs(c) for c in n.get("children", []) if c["type"] == "dir")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("-o", "--out", default="manifest.json")
    ap.add_argument("--max-files", type=int, default=300, help="폴더당 기록할 최대 파일 수")
    ap.add_argument("--hide", default="", help="숨길 파일/폴더명 정규식 (예: '개인|견적')")
    a = ap.parse_args()
    if not os.path.isdir(a.root):
        sys.exit(f"폴더가 없습니다: {a.root}")
    EXT, EXT_SIZE = Counter(), Counter()
    tree = walk(a.root, a.max_files, re.compile(a.hide) if a.hide else None)
    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "total_size": tree["size"], "total_size_h": human(tree["size"]),
        "total_files": tree["files"], "total_dirs": count_dirs(tree),
        "by_ext": [{"ext": k, "count": v, "size": EXT_SIZE[k]} for k, v in EXT.most_common()],
        "tree": tree,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK  {out['total_files']:,} files / {out['total_dirs']:,} folders / {out['total_size_h']}  ->  {a.out}")
    print("확장자 상위:", ", ".join(f"{e['ext']}={e['count']}" for e in out["by_ext"][:10]))
