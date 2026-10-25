"""stewpoly 릴스 댓글 → 단골 장부(data/guests.json)·주문 레일(data/rail.json) 갱신 → 빌드 → (선택) 배포

  py -3 tools/update_comments.py                      # data/reels.txt의 최근 릴스 댓글을 받아 갱신
  py -3 tools/update_comments.py --add <릴스 링크>     # 새 릴스를 reels.txt 맨 아래에 추가하고 갱신
  py -3 tools/update_comments.py --push               # 바뀐 게 있으면 커밋·푸시까지
  py -3 tools/update_comments.py --no-fetch           # 이미 받아 둔 comments.json으로만 다시 계산

댓글 받기는 본사 도구 `도구/인스타댓글.py fetch`를 그대로 쓴다(로그인이 풀리면 실패 → 진호님이 `py -3 도구/인스타댓글.py login`).
- 장부: 댓글을 단 릴스 수 = 방문 수(칭호 기준). 같은 댓글은 id로 한 번만 센다. stewpoly 자신의 댓글은 빼고, data/hide.txt의 아이디도 화면에서 뺀다
- 레일: 맨 아래(최신) 릴스의 최상위 댓글 중 좋아요 많은 순 8개. 링크·멘션만 있는 댓글·90자 넘는 댓글·data/blocklist.txt 단어가 든 댓글은 뺀다
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IG_TOOL = Path(r"C:/Users/jinho/Desktop/본사/도구/인스타댓글.py")
IG_OUT = Path(r"C:/Users/jinho/video/ig_comments")
OWN = {"stewpoly"}
RECENT = 6          # 매번 다시 받는 최근 릴스 수(오래된 릴스 댓글은 이미 장부에 들어 있음)
RAIL_N = 8

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site  # noqa: E402


def code_of(url):
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def fetch(url):
    r = subprocess.run([sys.executable, str(IG_TOOL), "fetch", url, "--max", "1000"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"[댓글 받기 실패] {url}\n{(r.stdout + r.stderr)[-600:]}")
        return False
    return True


def ok_for_rail(c, block, hide):
    t = (c.get("text") or "").strip()
    u = (c.get("username") or "").lower()
    if not t or u in OWN or u in hide or str(c.get("id")) in hide:
        return False
    if len(t) > 90 or re.search(r"https?://|www\.", t, re.I):
        return False
    if not re.sub(r"(@[\w.]+|\s)+", "", t):  # 친구 멘션만 있는 댓글
        return False
    low = t.lower()
    return not any(w in low for w in block)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()

    reels_file = DATA / "reels.txt"
    if a.add:
        if not code_of(a.add):
            sys.exit("릴스 링크가 아닙니다: " + a.add)
        cur = reels_file.read_text(encoding="utf-8")
        if code_of(a.add) not in cur:
            reels_file.write_text(cur.rstrip("\n") + "\n" + a.add.strip() + "\n", encoding="utf-8")
    reels = build_site.lines("reels.txt")
    if not reels:
        print("data/reels.txt에 릴스가 없습니다 — 빌드만 합니다")

    if not a.no_fetch:
        for url in reels[-RECENT:]:
            fetch(url)

    guests = build_site.load("guests.json", {"updated": None, "users": {}, "seen": []})
    seen = set(guests.get("seen", []))
    users = guests.setdefault("users", {})
    hide = {s.lower().lstrip("@") for s in build_site.lines("hide.txt")}
    block = [s.lower() for s in build_site.lines("blocklist.txt")]
    added = 0
    latest = None
    for url in reels:
        f = IG_OUT / (code_of(url) or "?") / "comments.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        if url == reels[-1]:
            latest = data
        for c in data.get("comments", []):
            cid, u = str(c.get("id")), c.get("username")
            if not u or u.lower() in OWN or cid in seen:
                continue
            seen.add(cid)
            g = users.setdefault(u, {"comments": 0, "reels": [], "first": c.get("time"), "last": c.get("time")})
            g["comments"] += 1
            # 칭호는 댓글 수가 아니라 댓글 단 릴스 수로 매긴다(한 릴스에 몰아 쓴 도배로 칭호를 못 올리게)
            code = data.get("code") or code_of(url)
            if code not in g.setdefault("reels", []):
                g["reels"].append(code)
            g["first"] = min(filter(None, [g.get("first"), c.get("time")]), default=None)
            g["last"] = max(filter(None, [g.get("last"), c.get("time")]), default=None)
            added += 1
    now = f"{datetime.now():%Y-%m-%d %H:%M}"
    guests["seen"] = sorted(seen)
    guests["updated"] = now
    (DATA / "guests.json").write_text(json.dumps(guests, ensure_ascii=False, indent=1), encoding="utf-8")

    if latest:
        top = sorted((c for c in latest.get("comments", []) if ok_for_rail(c, block, hide)),
                     key=lambda c: (-(c.get("likes") or 0), c.get("time") or ""))[:RAIL_N]
        rail = {"updated": now, "reel": latest.get("post"),
                "orders": [{"id": str(c["id"]), "username": c["username"], "text": c["text"].strip(), "likes": c.get("likes") or 0}
                           for c in top]}
        (DATA / "rail.json").write_text(json.dumps(rail, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"새 댓글 {added}개 반영, 단골 {len(users)}명")

    build_site.main()

    if a.push:
        git = lambda *args: subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")
        git("add", "data", "dishes.js", "ledger.js", "rail.js", "d", "img/cert")
        if git("diff", "--cached", "--quiet").returncode == 0:
            print("바뀐 것 없음 — 푸시 안 함")
            return
        r = git("commit", "-m", f"data: comments update {now}")
        p = git("push", "origin", "main")
        print("푸시 완료" if p.returncode == 0 else f"[푸시 실패] {p.stderr[-400:]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
