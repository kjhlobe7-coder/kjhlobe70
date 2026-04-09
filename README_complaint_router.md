# 민원 소관 부서 자동 분류 시스템

민원 문장을 입력하면 담당 가능성이 높은 부서를 자동 추천하는 시스템입니다.

## 구성

- `complaint_department_classifier.py`: 분류 엔진(키워드 가중치 기반)
- `complaint_api_server.py`: HTTP API 서버
- `department_rules.json`: 부서별 키워드/가중치 규칙

## 1) 콘솔에서 바로 사용

```bash
python complaint_department_classifier.py
```

입력 예시:

`집 앞 도로에 포트홀이 커서 차량 파손 위험이 큽니다.`

결과 예시:

- 추천 부서: `도로관리과`
- 신뢰도: `0.714`
- 매칭 키워드: `도로, 포트홀`

## 2) API 서버 실행

```bash
python complaint_api_server.py
```

### 상태 확인

```bash
curl http://127.0.0.1:8000/health
```

### 분류 요청

```bash
curl -X POST http://127.0.0.1:8000/classify ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"불법주정차 차량 때문에 버스가 통행을 못합니다\"}"
```

응답 예시:

```json
{
  "department": "교통행정과",
  "confidence": 0.75,
  "matched_keywords": ["버스", "불법주정차"],
  "candidates": [
    {"department": "교통행정과", "score": 8.0},
    {"department": "기획예산과", "score": 0.0},
    {"department": "복지정책과", "score": 0.0}
  ]
}
```

## 규칙 튜닝 방법

`department_rules.json`에서 부서별 `keywords`를 추가/수정하면 분류 성능을 개선할 수 있습니다.

예:

```json
"환경관리과": {
  "keywords": {
    "쓰레기": 4,
    "무단투기": 5,
    "악취": 5
  }
}
```
