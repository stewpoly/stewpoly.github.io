# stewpoly 사이트 운영법 (https://stewpoly.github.io)

댓글을 달게 하는 특전 사이트. 단골 장부·주문 레일·요리별 페이지(증서)는 `data/`의 json에서 자동으로 만들어진다.
**`dishes.js`·`ledger.js`·`rail.js`·`d/`·`img/cert/`는 자동 생성 파일이라 손으로 고치지 않는다.**
명령은 이 폴더(`본사/콘텐츠디자인파트/작업/stewpoly_site`)에서 실행한다.

## 1. 새 릴스를 올렸을 때 (댓글 → 장부·레일 갱신 + 배포)
```
py -3 tools/update_comments.py --add https://www.instagram.com/reel/XXXX/ --push
```
- 릴스 링크를 `data/reels.txt` 맨 아래에 추가하고, 최근 릴스 6개의 댓글을 `도구/인스타댓글.py`로 받아 장부·레일을 갱신한 뒤 빌드·커밋·푸시까지 한다
- 평소 갱신(새 릴스 없이): `py -3 tools/update_comments.py --push`
- 「로그인 필요」로 실패하면 진호님께 PC에서 `py -3 도구/인스타댓글.py login`을 부탁한다
- 주문 레일은 맨 아래(최신) 릴스의 좋아요 많은 댓글 8개

## 2. 요리를 완성했을 때 (메뉴판·요리 페이지·증서)
1. 정방형 사진(900px 이상 jpg, 영문 소문자 파일명)을 `img/`에 넣는다
2. `data/dishes.json` **맨 위**에 항목 추가:
```json
{
  "slug": "wolf-pup-porridge",
  "name": "Wolf Pup Porridge",
  "note": "한 줄 설명(영어)",
  "ingredients": ["moon oats", "pup biscuits"],
  "orderedBy": "",
  "requester": "주문한사람아이디(@ 없이)",
  "date": "2026-10-26",
  "image": "img/wolf-pup-porridge.jpg",
  "reel": "https://www.instagram.com/reel/XXXX/"
}
```
3. `py -3 tools/update_comments.py --no-fetch --push` (또는 빌드만 `py -3 tools/build_site.py` 후 직접 커밋·푸시)
- 페이지 `d/<slug>/`와 증서 `img/cert/<slug>.jpg`(1080×1920 스토리 크기)가 자동으로 생긴다. 요청자는 장부에서 ★ Honored Guest로 맨 위에 오른다
- 증서 링크를 요청자 답글·DM에 줄 때: `https://stewpoly.github.io/d/<slug>/`
- `requester`가 없으면(하우스 메뉴 등) `orderedBy` 글자가 그대로 쓰인다

## 3. 빼고 싶은 이름·댓글
- `data/hide.txt`: 인스타 아이디나 댓글 id를 한 줄에 하나 → 장부·레일 모두에서 빠진다
- `data/blocklist.txt`: 이 단어가 든 댓글은 레일에 안 오른다(장부 이름은 남음)
- 고친 뒤 `py -3 tools/update_comments.py --no-fetch --push`

## 4. 규칙
- 칭호: 댓글 단 **릴스 수** 기준 Wanderer 1 · Regular 3+ · Guild Chef 7+ · 요리가 만들어지면 ★ Honored Guest (한 릴스에 몰아 쓴 도배는 1회로 셈)
- 프로필 사진은 쓰지 않고 아이디만 공개한다. 본인이 빼 달라면 hide.txt에 넣는다
- stewpoly 자신의 댓글은 세지 않는다
- 매일 자동 갱신 예약은 아직 없음(첫 릴스 이후 작업 스케줄러에 걸 예정, 정비 담당)
