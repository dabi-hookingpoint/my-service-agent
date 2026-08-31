"""
후킹포인트 문의 서비스 에이전트 — 실제 도구 구현 (실습용).

design-packet.md ②의 4개 도구 계약을 그대로 코드로 옮긴 것.
가짜 결과를 만들어내지 않기 위해, 실제 데이터 파일(chunks.json / ip_access_grants.json /
inquiries.log.json)을 읽고 쓴다. LLM 호출 없이 순수 함수로만 구현했다 —
"어떤 도구를 언제 쓸지"는 트레이스를 만들 때 에이전트 역할(Claude)이 직접 판단한다.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CHUNKS_PATH = DATA_DIR / "chunks.json"
IP_ACCESS_PATH = DATA_DIR / "ip_access_grants.json"
INQUIRIES_PATH = DATA_DIR / "inquiries.log.json"

VALID_CATEGORIES = {"제작", "기획", "편집", "후반문의", "회사정보"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _load_chunks():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_ip_grants():
    with open(IP_ACCESS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_inquiries():
    if not INQUIRIES_PATH.exists():
        return []
    with open(INQUIRIES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_inquiries(items):
    with open(INQUIRIES_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def search_policy(category: str, query: str, top_k: int = 5) -> dict:
    """조회. design-packet.md 도구 1."""
    if not category or not query:
        return {"error": "MISSING_ARG", "message": "category와 query가 모두 필요합니다."}
    if category not in VALID_CATEGORIES:
        return {"error": "MISSING_ARG", "message": f"category는 {sorted(VALID_CATEGORIES)} 중 하나여야 합니다."}

    chunks = _load_chunks()
    q_tokens = [t for t in re.split(r"\s+", query.strip()) if t]

    def score(c):
        text = f"{c['title']} {c['section']} {c['text']}"
        return sum(text.count(t) for t in q_tokens)

    candidates = [c for c in chunks if c["category"] == category]
    scored = sorted(((score(c), c) for c in candidates), key=lambda x: x[0], reverse=True)
    hits = [c for s, c in scored if s > 0][:top_k]

    if not hits:
        return {"error": "NOT_FOUND", "results": []}

    def label(source: str) -> str:
        if source == "후킹포인트":
            return "후킹포인트공식"
        if source == "대표확인":
            return "대표확인"
        return "업계일반"

    results = [
        {
            "title": c["title"],
            "section": c["section"],
            "source_label": label(c["source"]),
            "snippet": c["text"][:140],
            "url": c["url"],
        }
        for c in hits
    ]
    return {"results": results}


def check_lineup_status() -> dict:
    """조회. design-packet.md 도구 2."""
    chunks = _load_chunks()
    fact = next((c for c in chunks if c["id"] == "hookingpoint-facts-lineup-current-production"), None)
    if not fact:
        return {"error": "TOOL_ERROR", "message": "라인업 데이터를 찾을 수 없습니다."}
    return {
        "summary_text": "예술영화 1편, 저예산 상업영화 1편, 드라마 2편, 숏폼 드라마 1편 준비 중",
        "disclosed_at": fact["fetched_at"],
    }


def check_ip_access(contact_email: str) -> dict:
    """조회. design-packet.md 도구 3."""
    if not contact_email or not EMAIL_RE.match(contact_email):
        return {"error": "MISSING_ARG", "message": "유효한 contact_email이 필요합니다."}
    grants = _load_ip_grants()
    status = grants.get(contact_email, "none")
    notes = {
        "granted": "열람 권한이 부여되어 있습니다.",
        "pending": "열람 신청이 접수되어 담당자 확인 대기 중입니다.",
        "none": "열람 신청 기록이 없습니다.",
    }
    return {"status": status, "note": notes[status]}


def submit_inquiry(category: str, contact_email: str, message: str) -> dict:
    """쓰기. design-packet.md 도구 4. 호출 전 사용자 확인을 반드시 거쳐야 한다(③ 권한과 승인)."""
    missing = []
    if not category or category not in VALID_CATEGORIES:
        missing.append("category")
    if not contact_email or not EMAIL_RE.match(contact_email):
        missing.append("contact_email")
    if not message or not (1 <= len(message) <= 1000):
        missing.append("message")
    if missing:
        return {"error": "MISSING_ARG", "message": f"누락/형식 오류: {', '.join(missing)}"}

    inquiries = _load_inquiries()
    inquiry_id = f"inq-{uuid.uuid4().hex[:8]}"
    inquiries.append(
        {
            "inquiry_id": inquiry_id,
            "category": category,
            "contact_email": contact_email,
            "message": message,
            "status": "접수됨",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    _save_inquiries(inquiries)
    # 반환값에는 message 원문을 다시 담지 않는다 (⑤ 반환 형식 규약)
    return {"inquiry_id": inquiry_id, "status": "접수됨", "expected_response": "영업일 기준 2~3일"}


if __name__ == "__main__":
    import sys

    fn_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    fn = {
        "search_policy": search_policy,
        "check_lineup_status": check_lineup_status,
        "check_ip_access": check_ip_access,
        "submit_inquiry": submit_inquiry,
    }[fn_name]
    print(json.dumps(fn(**args), ensure_ascii=False, indent=2))
