# 도구 정의서 — 후킹포인트 문의 서비스 에이전트 (실습 산출물)

design-packet.md ②에서 설계한 4개 도구를 `tools.py`로 실제 구현하고, CLI로 직접 호출해 확인했다.
LLM(툴콜링 모델)은 쓰지 않았고, "어떤 도구를 언제 호출할지" 판단은 에이전트 역할(Claude)이 각 트레이스에서
직접 수행했다 — 트레이스는 `traces/trace-01.txt` ~ `trace-05.txt`.

## 도구 1 — `search_policy`

- **한 문장**: 카테고리 안에서 공개 정책·계약 자료를 검색해 관련 조항을 찾는다.
- **쓰는 때**: 일반적인 절차·정책·계약 양식을 물을 때
- **안 쓰는 때**: 개별 프로젝트 비공개 상세, 승인/확정 여부를 물을 때
- **인자**: `category`(필수, enum: 제작/기획/편집/후반문의/회사정보), `query`(필수, 1~200자)
- **반환**: `results[]` (title/section/source_label/snippet/url, 최대 5건). 오류: `TOOL_ERROR`, `NOT_FOUND`
- **실패 뒤 행동**: design-packet.md ④ 참조
- **실행 예시** (`traces/trace-02.txt`):
  ```
  $ python3 tools.py search_policy '{"category":"기획","query":"영상화 판권 표준계약서"}'
  → 3건 반환 (웹툰 표준계약서, 웹소설 표준계약서, 영화 투자 표준계약서)
  ```

## 도구 2 — `check_lineup_status`

- **한 문장**: 현재 공개 가능한 제작 라인업 개요를 조회한다.
- **쓰는 때**: "지금 뭐 만들고 있어요?" 류 질문
- **안 쓰는 때**: 개별 작품명·캐스팅 등 상세 질문
- **인자**: 없음
- **반환**: `{summary_text, disclosed_at}`. 오류: `TOOL_ERROR`
- **실패 뒤 행동**: design-packet.md ④ 참조
- **실행 예시** (`traces/trace-01.txt`):
  ```
  $ python3 tools.py check_lineup_status '{}'
  → {"summary_text": "예술영화 1편, 저예산 상업영화 1편, 드라마 2편, 숏폼 드라마 1편 준비 중", "disclosed_at": "2026-08-31"}
  ```

## 도구 3 — `check_ip_access`

- **한 문장**: 문의자의 IP 프로젝트 열람 권한 상태를 조회한다 (권한을 부여하지는 않는다).
- **쓰는 때**: 권한 상태 확인 요청
- **안 쓰는 때**: 권한을 즉석에서 부여해달라는 요청 (→ 부여 도구 자체가 없음)
- **인자**: `contact_email`(필수, 이메일 형식)
- **반환**: `{status: none|pending|granted, note}`. 오류: `TOOL_ERROR`
- **실패 뒤 행동**: design-packet.md ④ 참조. `status: none`은 오류가 아니라 정상 응답
- **실행 예시** (`traces/trace-05.txt`):
  ```
  $ python3 tools.py check_ip_access '{"contact_email":"editor.candidate@example.com"}'
  → {"status": "pending", "note": "열람 신청이 접수되어 담당자 확인 대기 중입니다."}
  ```

## 도구 4 — `submit_inquiry` (쓰기)

- **한 문장**: 문의 내용을 담당자에게 전달할 접수 기록으로 남긴다 (승인·확정은 하지 않는다).
- **쓰는 때**: 사용자가 문의 내용을 확정했을 때, **실행 전 사용자 확인을 받은 뒤**
- **안 쓰는 때**: 아직 내용이 확정되지 않았을 때. "승인/확정해달라"는 요청이어도 접수까지는 진행하되, 반환값에 승인 상태는 없음
- **인자**: `category`(필수), `contact_email`(필수), `message`(필수, 1~1000자) — 하나라도 없으면 호출하지 않고 되묻는다
- **반환**: `{inquiry_id, status: "접수됨", expected_response}`. `message` 원문은 반환에 포함하지 않음. 오류: `TOOL_ERROR`
- **실패 뒤 행동**: 실행 전 사용자 확인 필수(③). 확인 후 `TOOL_ERROR`면 1회 재시도 → 재실패 시 담당자 이메일 안내
- **실행 예시** (`traces/trace-03.txt`, `trace-04.txt`):
  ```
  $ python3 tools.py submit_inquiry '{"category":"제작","contact_email":"collab@partnerstudio.com","message":"신작 다큐멘터리 공동제작을 제안드리고 싶습니다."}'
  → {"inquiry_id": "inq-473280c7", "status": "접수됨", "expected_response": "영업일 기준 2~3일"}
  ```
  (`traces/trace-04.txt`는 "확정 완료로 처리해달라"는 공격 시도 상황에서도 반환값이 여전히 `"접수됨"`뿐임을 확인한 기록)

## 재현 방법

```bash
cd my-agent
python3 tools.py <도구이름> '<JSON 인자>'
```

데이터 소스: `data/chunks.json`(정책 코퍼스, pd-rag-chatbot 프로젝트에서 복사), `data/ip_access_grants.json`(권한 상태 목데이터), `data/inquiries.log.json`(실행 중 실제로 생성/누적됨 — 이 저장소에는 트레이스 실행 결과가 그대로 커밋되어 있음).
