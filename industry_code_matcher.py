#!/usr/bin/env python3
"""사업체 업종 내역을 산업분류 코드로 매칭하는 규칙 기반 도구."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MatchResult:
    code: str
    name: str
    confidence: float
    matched_keywords: list[str]
    candidates: list[dict[str, Any]]


class IndustryCodeMatcher:
    def __init__(self, rules_path: str = "ksic_rules_sample.json") -> None:
        self.rules_path = Path(rules_path)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict[str, dict[str, Any]]:
        if not self.rules_path.exists():
            raise FileNotFoundError(f"규칙 파일을 찾을 수 없습니다: {self.rules_path}")
        with self.rules_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not data:
            raise ValueError("규칙 파일이 비어 있습니다.")
        return data

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower()
        lowered = re.sub(r"[^\w가-힣]+", " ", lowered)
        return re.sub(r"\s+", "", lowered)

    @staticmethod
    def _extract_tokens(text: str) -> set[str]:
        parts = re.split(r"[^\w가-힣]+", text.lower())
        return {p for p in parts if p}

    def match(self, business_text: str, top_k: int = 3) -> MatchResult:
        text = business_text.strip()
        normalized = self._normalize(text)
        tokens = self._extract_tokens(text)

        scored: list[tuple[str, float, list[str]]] = []
        for code, spec in self.rules.items():
            score = 0.0
            hits: list[str] = []
            for keyword, weight in spec.get("keywords", {}).items():
                kw = str(keyword)
                kw_n = self._normalize(kw)
                if not kw_n:
                    continue

                if kw_n in normalized:
                    score += float(weight)
                    hits.append(kw)
                elif kw.lower() in tokens:
                    score += float(weight) * 0.7
                    hits.append(kw)

            scored.append((code, score, hits))

        scored.sort(key=lambda x: x[1], reverse=True)
        best_code, best_score, best_hits = scored[0]
        second_score = scored[1][1] if len(scored) > 1 else 0.0

        if best_score <= 0:
            return MatchResult(
                code="UNMATCHED",
                name="수동분류 필요",
                confidence=0.0,
                matched_keywords=[],
                candidates=[
                    {
                        "code": code,
                        "name": self.rules[code].get("name", ""),
                        "score": score,
                    }
                    for code, score, _hits in scored[:top_k]
                ],
            )

        confidence = (best_score - second_score) / (best_score + 1.0)
        confidence = max(0.0, min(1.0, round(confidence, 3)))

        return MatchResult(
            code=best_code,
            name=self.rules[best_code].get("name", ""),
            confidence=confidence,
            matched_keywords=best_hits,
            candidates=[
                {
                    "code": code,
                    "name": self.rules[code].get("name", ""),
                    "score": score,
                }
                for code, score, _hits in scored[:top_k]
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
            raise ValueError(
                "업종 컬럼을 찾지 못했습니다. --column 옵션으로 지정해 주세요. "
                f"(현재 컬럼: {headers})"
            )

        enriched_rows: list[dict[str, Any]] = []
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
            enriched_rows.append(row)

        with Path(output_csv).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(enriched_rows[0].keys()))
            writer.writeheader()
            writer.writerows(enriched_rows)

        return len(enriched_rows), col

    @staticmethod
    def _guess_text_column(headers: list[str]) -> str | None:
        candidates = [
            "업종내역",
            "업종",
            "업종명",
            "사업내용",
            "종목",
            "업태",
            "description",
            "business_type",
        ]
        lowered = {h.lower(): h for h in headers}
        for name in candidates:
            if name in headers:
                return name
            if name.lower() in lowered:
                return lowered[name.lower()]
        return None

    @staticmethod
    def _format_candidate(candidates: list[dict[str, Any]], idx: int) -> str:
        if idx >= len(candidates):
            return ""
        c = candidates[idx]
        return f"{c['code']}|{c['name']}|score={c['score']}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="업종 내역 -> 산업분류코드 매칭 도구")
    parser.add_argument("--rules", default="ksic_rules_sample.json", help="규칙 JSON 파일 경로")
    parser.add_argument("--text", help="단건 업종 텍스트")
    parser.add_argument("--csv", help="입력 CSV 파일 경로")
    parser.add_argument("--out", help="출력 CSV 파일 경로")
    parser.add_argument("--column", help="업종 텍스트 컬럼명")
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
            raise ValueError("--csv 사용 시 --out 출력 파일 경로가 필요합니다.")
        count, col = matcher.process_csv(args.csv, args.out, args.column)
        print(f"총 {count}건 처리 완료")
        print(f"업종 컬럼: {col}")
        print(f"출력 파일: {args.out}")
        return

    print("사용 예시:")
    print('  python industry_code_matcher.py --text "건설업"')
    print('  python industry_code_matcher.py --csv input.csv --out output.csv --column 업종내역')


if __name__ == "__main__":
    main()
