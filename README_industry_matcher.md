# 사업체 업종 -> 산업분류 코드 매칭기

사업체 업종 내역 텍스트를 입력하면 규칙 기반으로 산업분류 코드를 추천합니다.

## 파일 구성

- `industry_code_matcher.py`: 매칭 엔진 + CLI + CSV 일괄처리
- `ksic_index_full.json`: KSIC 제11차 전체 분류 데이터(통계청 원문에서 추출)
- `scripts/build_ksic_index.ps1`: 통계청 원문을 다시 내려받아 `ksic_index_full.json`을 재생성하는 스크립트
- `ksic_rules_sample.json`: 간단 샘플 규칙(백업용)

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

## 데이터 갱신

공식 원문에서 전체 분류 데이터를 다시 생성하려면:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_ksic_index.ps1
```

## 규칙/매칭 튜닝

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

- 기본 매칭은 `ksic_index_full.json`(KSIC 제11차 전체 분류 데이터) 기반으로 동작합니다.
- 실제 색인(유의어)까지 100% 반영하려면 통계분류포털의 색인 테이블 원문이 추가로 필요하며, 현재는 공식 분류 항목표 전량 반영 + 텍스트 유사 매칭 방식입니다.
- 공식 출처:
  - https://kostat.go.kr/board.es?act=view&bid=107&list_no=428660&mid=a10403040000&ref_bid=&tag=
  - https://kssc.kostat.go.kr
