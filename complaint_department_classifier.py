#!/usr/bin/env python3
"""민원 내용을 소관 부서로 분류하는 간단한 규칙 기반 분류기."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ClassificationResult:
    complaint: str
    department: str
    confidence: float
    matched_keywords: list[str]
    candidates: list[dict[str, float]]


class ComplaintDepartmentClassifier:
    def __init__(self, rules_path: str = "department_rules.json") -> None:
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
        return re.sub(r"\s+", "", text.lower())

    def classify(self, complaint_text: str, top_k: int = 3) -> ClassificationResult:
        normalized = self._normalize(complaint_text)
        scores: dict[str, float] = {}
        keyword_hits: dict[str, list[str]] = {}

        for department, config in self.rules.items():
            score = 0.0
            hits: list[str] = []
            keywords: dict[str, int] = config.get("keywords", {})
            for keyword, weight in keywords.items():
                if self._normalize(keyword) in normalized:
                    score += float(weight)
                    hits.append(keyword)
            scores[department] = score
            keyword_hits[department] = hits

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_department, top_score = sorted_scores[0]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

        if top_score <= 0:
            return ClassificationResult(
                complaint=complaint_text,
                department="민원총괄(수동분류)",
                confidence=0.0,
                matched_keywords=[],
                candidates=[{"department": d, "score": s} for d, s in sorted_scores[:top_k]],
            )

        confidence = round((top_score - second_score) / (top_score + 1.0), 3)
        confidence = max(0.0, min(confidence, 1.0))

        return ClassificationResult(
            complaint=complaint_text,
            department=top_department,
            confidence=confidence,
            matched_keywords=keyword_hits[top_department],
            candidates=[{"department": d, "score": s} for d, s in sorted_scores[:top_k]],
        )


def _pretty_print(result: ClassificationResult) -> None:
    print("\n=== 분류 결과 ===")
    print(f"민원: {result.complaint}")
    print(f"추천 부서: {result.department}")
    print(f"신뢰도: {result.confidence:.3f}")
    print(f"매칭 키워드: {', '.join(result.matched_keywords) if result.matched_keywords else '(없음)'}")
    print("후보 부서:")
    for candidate in result.candidates:
        print(f"- {candidate['department']}: {candidate['score']}")


def main() -> None:
    classifier = ComplaintDepartmentClassifier()
    print("민원 소관 부서 분류기입니다. 종료하려면 빈 줄을 입력하세요.")

    while True:
        text = input("\n민원 내용을 입력하세요: ").strip()
        if not text:
            print("분류기를 종료합니다.")
            break
        result = classifier.classify(text)
        _pretty_print(result)


if __name__ == "__main__":
    main()
