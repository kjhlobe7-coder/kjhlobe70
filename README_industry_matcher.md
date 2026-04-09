# 사업체 업종 -> 산업분류 코드 매칭기

사업체 업종 내역 텍스트를 입력하면 규칙 기반으로 산업분류 코드를 추천합니다.

## 파일 구성

- `industry_code_matcher.py`: 매칭 엔진 + CLI + CSV 일괄처리
- `ksic_rules_sample.json`: 업종 키워드 규칙 샘플

## 1) 단건 매칭

```bash
python industry_code_matcher.py --text "스마트스토어로 생활용품 온라인 판매"
```

출력:

- 추천 코드
- 산업분류명
- 신뢰도
- 매칭 키워드
- 후보 3개

## 2) CSV 일괄 매칭

입력 CSV에 `업종내역`(또는 `업종`, `업종명`, `사업내용`, `종목`, `업태`) 컬럼이 있으면 자동 인식합니다.

```bash
python industry_code_matcher.py --csv input.csv --out output.csv
```

직접 컬럼 지정:

```bash
python industry_code_matcher.py --csv input.csv --out output.csv --column 업종내역
```

출력 CSV에 아래 컬럼이 추가됩니다.

- `매칭코드`
- `산업분류명`
- `신뢰도`
- `매칭키워드`
- `후보1`, `후보2`, `후보3`

## 규칙 튜닝

`ksic_rules_sample.json`에서 코드별 `keywords`를 수정/추가하면 정확도를 높일 수 있습니다.

예:

```json
"62010": {
  "name": "컴퓨터 프로그래밍 서비스업",
  "keywords": {
    "앱개발": 7,
    "웹개발": 7,
    "소프트웨어개발": 8
  }
}
```

## 참고

현재 규칙 파일은 바로 사용 가능한 샘플입니다. 실제 운영 환경에서는 보유한 표준 산업분류 코드 마스터(전체 코드표)로 규칙을 확장해 정확도를 높이는 것을 권장합니다.
