#!/usr/bin/env python3
"""사업체 업종 내역을 KSIC 코드로 매칭하는 도구.

기본 데이터는 `ksic_index_full.json`(통계청 제11차 원문 기반 추출)을 사용한다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STOPWORDS = {
    "제조",
    "제조업",
    "서비스",
    "서비스업",
    "업",
    "업종",
    "기타",
    "및",
    "도매",
    "소매",
}


@dataclass
class MatchResult:
    code: str
    name: str
    confidence: float
    matched_keywords: list[str]
    candidates: list[dict[str, Any]]


class IndustryCodeMatcher:
    def __init__(self, rules_path: str = "ksic_index_full.json") -> None:
        self.rules_path = Path(rules_path)
        self.index_items = self._load_items()

    def _load_items(self) -> list[dict[str, str]]:
        if not self.rules_path.exists():
            fallback = Path("ksic_rules_sample.json")
            if fallback.exists():
                with fallback.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                return [{"code": code, "name": v.get("name", code)} for code, v in data.items()]
            raise FileNotFoundError(f"규칙/색인 파일을 찾을 수 없습니다: {self.rules_path}")

        with self.rules_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # full index format
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return [{"code": str(it["code"]), "name": str(it["name"])} for it in data["items"] if "code" in it and "name" in it]

        # legacy rule format
        if isinstance(data, dict):
            return [{"code": code, "name": v.get("name", code)} for code, v in data.items()]

        raise ValueError("지원하지 않는 데이터 형식입니다.")

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower()
        lowered = re.sub(r"[^\w가-힣]+", " ", lowered)
        return re.sub(r"\s+", "", lowered)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        raw = re.split(r"[^\w가-힣]+", text.lower())
        out: list[str] = []
        for t in raw:
            t = t.strip()
            if not t:
                continue
            if t in STOPWORDS:
                continue
            if len(t) < 2:
                continue
            out.append(t)
        return out

    def _score_item(self, input_text: str, code: str, name: str) -> tuple[float, list[str]]:
        input_norm = self._normalize(input_text)
        name_norm = self._normalize(name)
        input_tokens = self._tokens(input_text)
        name_tokens = self._tokens(name)

        score = 0.0
        hits: list[str] = []

        if input_norm == name_norm:
            score += 20.0
            hits.append(name)
        elif input_norm and input_norm in name_norm:
            score += 12.0
            hits.append(input_text.strip())
        elif name_norm and name_norm in input_norm:
            score += 8.0
            hits.append(name)

        for tok in set(name_tokens):
            if tok in input_norm:
                score += min(8.0, 1.5 + len(tok) * 0.8)
                hits.append(tok)

        for tok in set(input_tokens):
            if tok in name_norm:
                score += min(6.0, 1.0 + len(tok) * 0.7)
                hits.append(tok)

        # 코드 자체 검색 보너스
        if code.lower() in input_text.lower():
            score += 10.0
            hits.append(code)

        # 너무 포괄적인 대분류 문자코드는 점수 소폭 감산
        if re.fullmatch(r"[A-U]", code):
            score *= 0.85

        dedup_hits = sorted(set(hits), key=lambda x: (len(x), x), reverse=True)
        return score, dedup_hits[:6]

    def match(self, business_text: str, top_k: int = 3) -> MatchResult:
        text = business_text.strip()
        scored: list[tuple[str, str, float, list[str]]] = []

        for item in self.index_items:
            code = item["code"]
            name = item["name"]
            score, hits = self._score_item(text, code, name)
            scored.append((code, name, score, hits))

        scored.sort(key=lambda x: x[2], reverse=True)
        best_code, best_name, best_score, best_hits = scored[0]
        second_score = scored[1][2] if len(scored) > 1 else 0.0

        if best_score <= 0:
            return MatchResult(
                code="UNMATCHED",
                name="수동분류 필요",
                confidence=0.0,
                matched_keywords=[],
                candidates=[],
            )

        confidence = (best_score - second_score) / (best_score + 1.0)
        confidence = max(0.0, min(1.0, round(confidence, 3)))

        return MatchResult(
            code=best_code,
            name=best_name,
            confidence=confidence,
            matched_keywords=best_hits,
            candidates=[
                {"code": code, "name": name, "score": round(score, 3)}
                for code, name, score, _hits in scored[:top_k]
            ],
        )

    def process_csv(self, input_csv: str, output_csv: str, text_column: str | None = None) -> tuple[int, str]:
        input_path = Path(input_csv)
        if not input_path.exists():
            raise FileNotFoundError(f"입력 CSV를 찾을 수 없습니다: {input_csv}")

        with input_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            headers = reader.fieldnames or []

        if not rows:
            raise ValueError("입력 CSV에 데이터가 없습니다.")

        col = text_column or self._guess_text_column(headers)
        if not col:
            raise ValueError(f"업종 컬럼을 찾지 못했습니다. --column으로 지정하세요. (현재: {headers})")

        out_rows: list[dict[str, Any]] = []
        for row in rows:
            text = (row.get(col) or "").strip()
            result = self.match(text)
            row["매칭코드"] = result.code
            row["산업분류명"] = result.name
            row["신뢰도"] = result.confidence
            row["매칭키워드"] = ",".join(result.matched_keywords)
            row["후보1"] = self._format_candidate(result.candidates, 0)
            row["후보2"] = self._format_candidate(result.candidates, 1)
            row["후보3"] = self._format_candidate(result.candidates, 2)
            out_rows.append(row)

        with Path(output_csv).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            writer.writeheader()
            writer.writerows(out_rows)

        return len(out_rows), col

    @staticmethod
    def _guess_text_column(headers: list[str]) -> str | None:
        candidates = ["업종내역", "업종", "업종명", "사업내용", "종목", "업태", "description", "business_type"]
        lowered = {h.lower(): h for h in headers}
        for c in candidates:
            if c in headers:
                return c
            if c.lower() in lowered:
                return lowered[c.lower()]
        return None

    @staticmethod
    def _format_candidate(candidates: list[dict[str, Any]], idx: int) -> str:
        if idx >= len(candidates):
            return ""
        c = candidates[idx]
        return f"{c['code']}|{c['name']}|score={c['score']}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="업종 내역 -> 산업분류코드 매칭 도구")
    parser.add_argument("--rules", default="ksic_index_full.json", help="규칙/색인 JSON 경로")
    parser.add_argument("--text", help="단건 업종 텍스트")
    parser.add_argument("--csv", help="입력 CSV 경로")
    parser.add_argument("--out", help="출력 CSV 경로")
    parser.add_argument("--column", help="업종 컬럼명")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    matcher = IndustryCodeMatcher(rules_path=args.rules)

    if args.text:
        result = matcher.match(args.text)
        print("=== 매칭 결과 ===")
        print(f"입력: {args.text}")
        print(f"추천 코드: {result.code}")
        print(f"산업분류명: {result.name}")
        print(f"신뢰도: {result.confidence:.3f}")
        print(f"매칭 키워드: {', '.join(result.matched_keywords) if result.matched_keywords else '(없음)'}")
        print("후보:")
        for c in result.candidates:
            print(f"- {c['code']} | {c['name']} | score={c['score']}")
        return

    if args.csv:
        if not args.out:
            raise ValueError("--csv 사용 시 --out 경로가 필요합니다.")
        count, col = matcher.process_csv(args.csv, args.out, args.column)
        print(f"총 {count}건 처리 완료")
        print(f"업종 컬럼: {col}")
        print(f"출력 파일: {args.out}")
        return

    print("사용 예시:")
    print('  python industry_code_matcher.py --text "자동차 제조"')
    print('  python industry_code_matcher.py --csv input.csv --out output.csv --column 업종내역')


if __name__ == "__main__":
    main()
