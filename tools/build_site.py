"""stewpoly 사이트 빌드: data/*.json → 화면용 js, 요리별 페이지 d/<slug>/, 주문 완료 증서 img/cert/<slug>.jpg

  py -3 tools/build_site.py            # 바뀐 것만(증서는 내용이 바뀐 요리만 다시 찍음)
  py -3 tools/build_site.py --force    # 증서 전부 다시

새 요리를 올리는 법: img/에 정방형 사진(900px 이상 jpg)을 넣고 data/dishes.json 맨 위에 항목을 추가한 뒤 이 스크립트를 돌린다.
  slug: 영문 소문자-하이픈(페이지 주소 d/<slug>/), requester: 주문한 사람 인스타 아이디(@ 없이, 단골 장부 연결), reel: 그 요리 릴스 링크
"""
import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TPL = ROOT / "tools" / "templates"
SITE = "https://stewpoly.github.io"


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def lines(name):
    p = DATA / name
    if not p.exists():
        return []
    return [s.strip() for s in p.read_text(encoding="utf-8").splitlines() if s.strip() and not s.startswith("#")]


def order_no(s):  # 사이트 주문서와 같은 계산
    h = 7
    for c in s.lower():
        h = (h * 31 + ord(c)) % 9973
    return f"No. {h:04d}"


def write_js(name, var, obj):
    body = json.dumps(obj, ensure_ascii=False, indent=1)
    (ROOT / name).write_text(f"// 자동 생성 파일 — 고치지 말고 data/ 아래 json을 고친 뒤 py -3 tools/build_site.py\nwindow.{var} = {body};\n",
                             encoding="utf-8")


def by_label(d):
    return "@" + d["requester"] if d.get("requester") else d.get("orderedBy") or "House special"


def build_pages(dishes):
    tpl = Template((TPL / "dish.html").read_text(encoding="utf-8"))
    e = lambda s: html.escape(str(s), quote=True)
    for d in dishes:
        reel = d.get("reel") or ""
        out = tpl.substitute(
            name=e(d["name"]), by=e(by_label(d)), slug=e(d["slug"]), image=e(d["image"]), date=e(d.get("date", "")),
            note=e(d.get("note", "")), number=e(order_no(d["name"])),
            tags="".join(f"<span>{e(t)}</span>" for t in d.get("ingredients", [])),
            reelbtn=f'<a class="btn" href="{e(reel)}" target="_blank" rel="noopener">Watch it cooked</a>' if reel else "")
        p = ROOT / "d" / d["slug"] / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(out, encoding="utf-8")


def build_certs(dishes, force=False):
    stamp_file = ROOT / "img" / "cert" / "_hash.json"
    stamps = json.loads(stamp_file.read_text(encoding="utf-8")) if stamp_file.exists() else {}
    tpl = Template((TPL / "cert.html").read_text(encoding="utf-8"))
    todo = []
    for d in dishes:
        key = hashlib.sha1(json.dumps([d["name"], by_label(d), d.get("date"), d["image"],
                                       (TPL / "cert.html").stat().st_mtime], ensure_ascii=False).encode()).hexdigest()[:12]
        jpg = ROOT / "img" / "cert" / f"{d['slug']}.jpg"
        if force or stamps.get(d["slug"]) != key or not jpg.exists():
            todo.append((d, key, jpg))
    if not todo:
        return 0
    from playwright.sync_api import sync_playwright
    from PIL import Image
    tmp = ROOT / "tools" / "_cert_tmp.html"
    e = lambda s: html.escape(str(s), quote=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        for d, key, jpg in todo:
            tmp.write_text(tpl.substitute(name=e(d["name"]), by=e(by_label(d)), date=e(d.get("date", "")),
                                          image=e(d["image"]), number=e(order_no(d["name"]))), encoding="utf-8")
            pg.goto(tmp.as_uri(), wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            png = jpg.with_suffix(".png")
            pg.screenshot(path=str(png))
            Image.open(png).convert("RGB").save(jpg, quality=88)
            png.unlink()
            stamps[d["slug"]] = key
        b.close()
    tmp.unlink(missing_ok=True)
    stamp_file.write_text(json.dumps(stamps, indent=1), encoding="utf-8")
    return len(todo)


def main(force=False):
    dishes = load("dishes.json", [])
    guests = load("guests.json", {"updated": None, "users": {}, "seen": []})
    rail = load("rail.json", {"updated": None, "reel": None, "orders": []})
    hide = {s.lower().lstrip("@") for s in lines("hide.txt")}

    slugs = [d["slug"] for d in dishes]
    if len(slugs) != len(set(slugs)):
        sys.exit("dishes.json에 같은 slug가 두 번 있습니다")

    served = {}
    for d in dishes:
        if d.get("requester"):
            served.setdefault(d["requester"].lower(), []).append({"name": d["name"], "slug": d["slug"]})
    # 릴스 대장: reels.txt 순서 = 게시 순서. 요리가 된 릴스는 요리 이름을 라벨로 쓴다
    code = lambda url: (re.search(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url or "") or [None, None])[1]
    dish_by_code = {code(d.get("reel")): d["name"] for d in dishes if code(d.get("reel"))}
    reel_list = []
    for u in lines("reels.txt"):
        c = code(u)
        if c:
            reel_list.append({"code": c, "label": dish_by_code.get(c) or f"Reel {len(reel_list) + 1}", "url": u})
    rows = []
    for u, g in guests.get("users", {}).items():
        if u.lower() in hide:
            continue
        rows.append({"name": u, "visits": len(g.get("reels", [])) or 1, "comments": g.get("comments", 1),
                     "reels": g.get("reels", []), "first": g.get("first"), "last": g.get("last"),
                     "served": served.get(u.lower(), [])})
    # 채택된 사람이 먼저, 그다음 방문(댓글 단 릴스) 많은 순, 같으면 댓글 많은 순, 같으면 먼저 온 순
    rows.sort(key=lambda r: (-len(r["served"]), -r["visits"], -r["comments"], r["first"] or ""))
    write_js("ledger.js", "LEDGER", {"updated": guests.get("updated"), "reels": reel_list, "guests": rows})

    orders = [o for o in rail.get("orders", []) if o["username"].lower() not in hide and str(o.get("id")) not in hide]
    write_js("rail.js", "RAIL", {"updated": rail.get("updated"), "reel": rail.get("reel"), "orders": orders})

    write_js("dishes.js", "DISHES", [{**d, "by": by_label(d)} for d in dishes])
    build_pages(dishes)
    n = build_certs(dishes, force)
    print(f"빌드 완료: 요리 {len(dishes)}개(증서 새로 찍음 {n}), 단골 {len(rows)}명, 레일 {len(orders)}건 — {datetime.now():%H:%M}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    main(ap.parse_args().force)
