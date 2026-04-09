#!/usr/bin/env python3
"""KSIC industry code matcher (KSIC 11th index based)."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STOPWORDS = {
    "업",
    "업종",
    "산업",
    "산업분류",
    "분류",
    "사업",
    "사업체",
    "회사",
    "기업",
    "제조",
    "제조업",
    "도매",
    "소매",
    "판매",
    "서비스",
    "서비스업",
    "기타",
    "관련",
}

INTENT_TOKENS = {
    "제조": {"제조", "생산", "가공", "조립", "fabrication", "manufacturing"},
    "판매": {"판매", "유통", "도매", "소매", "쇼핑몰", "retail", "wholesale"},
    "수리": {"수리", "정비", "보수", "repair"},
    "공사": {"공사", "시공", "건설", "설치", "건축", "토목"},
    "운송": {"운송", "물류", "배송", "택배", "화물", "여객", "운반"},
}

SYNONYM_GROUPS = {
    # retail / distribution
    "정수기": {"가전", "가전제품", "생활가전", "소형가전", "주방가전"},
    "공기청정기": {"가전", "가전제품", "생활가전"},
    "비데": {"가전", "가전제품", "생활가전"},
    "냉장고": {"가전", "가전제품"},
    "세탁기": {"가전", "가전제품"},
    "tv": {"가전", "가전제품", "전자제품"},
    "전자상거래": {"온라인", "인터넷", "쇼핑몰", "이커머스"},
    "쇼핑몰": {"전자상거래", "온라인", "인터넷", "이커머스"},
    # mobility / machinery
    "자동차": {"차량", "모빌리티", "완성차"},
    "오토바이": {"이륜차", "모터사이클"},
    "지게차": {"산업용", "운반장비", "건설기계"},
    # construction / materials
    "건설": {"공사", "시공", "건축", "토목"},
    "시멘트": {"건설자재", "비금속", "광물제품"},
    "유리": {"비금속", "광물제품", "판유리"},
    "창호": {"유리", "샤시", "건설자재"},
    # food / beverage
    "카페": {"커피", "음료", "음료점"},
    "베이커리": {"제과", "제빵", "빵"},
    "치킨": {"음식점", "외식", "배달"},
    # ICT / professional
    "소프트웨어": {"소프트웨어개발", "프로그램", "개발", "it"},
    "앱개발": {"소프트웨어", "프로그램", "개발", "it"},
    "데이터센터": {"서버", "호스팅", "클라우드"},
    # healthcare / beauty
    "병원": {"의료", "의원", "진료"},
    "약국": {"의약품", "의료"},
    "화장품": {"뷰티", "미용", "코스메틱"},
}


def normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    cleaned = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_tokens(text: str, *, remove_stopwords: bool = True) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    out: list[str] = []
    for token in normalized.split(" "):
        token = token.strip()
        if len(token) < 2:
            continue
        if remove_stopwords and token in STOPWORDS:
            continue
        out.append(token)
    return out


def infer_intents(tokens: list[str]) -> set[str]:
    hit: set[str] = set()
    for token in tokens:
        for intent, words in INTENT_TOKENS.items():
            if token in words:
                hit.add(intent)
    return hit


def expand_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    seen = set(expanded)
    for token in tokens:
        aliases = SYNONYM_GROUPS.get(token, set())
        for alias in aliases:
            if alias not in seen:
                seen.add(alias)
                expanded.append(alias)
    return expanded


@dataclass
class Candidate:
    code: str
    name: str
    score: float
    matched_keywords: list[str]


class IndustryCodeMatcher:
    def __init__(self, index_path: str | Path = "ksic_index_full.json") -> None:
        self.index_path = Path(index_path)
        self.items = self._load_index()

    def _load_index(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            raise FileNotFoundError(f"index file not found: {self.index_path}")
        data = json.loads(self.index_path.read_text(encoding="utf-8-sig"))
        items = data.get("items", [])
        if not isinstance(items, list):
            raise ValueError("ksic index format error: items must be list")
        normalized_items: list[dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("code", "")).strip()
            name = str(raw.get("name", "")).strip()
            if not code or not name:
                continue
            notes = [str(x).strip() for x in raw.get("notes", []) if str(x).strip()]
            include_notes = [str(x).strip() for x in raw.get("include_notes", []) if str(x).strip()]
            exclude_notes = [str(x).strip() for x in raw.get("exclude_notes", []) if str(x).strip()]
            example_notes = [str(x).strip() for x in raw.get("example_notes", []) if str(x).strip()]
            normalized_items.append(
                {
                    "code": code,
                    "name": name,
                    "name_norm": normalize_text(name),
                    "notes": notes,
                    "include_notes": include_notes,
                    "exclude_notes": exclude_notes,
                    "example_notes": example_notes,
                }
            )
        return normalized_items

    @staticmethod
    def _token_overlap_score(input_tokens: list[str], text_tokens: set[str], per_token: float) -> tuple[float, list[str]]:
        score = 0.0
        hits: list[str] = []
        for token in input_tokens:
            if token in text_tokens:
                score += min(per_token + len(token) * 0.3, per_token + 2.0)
                hits.append(token)
        return score, hits

    @staticmethod
    def _text_match_score(query_norm: str, target_norm: str) -> float:
        if not query_norm or not target_norm:
            return 0.0
        if query_norm == target_norm:
            return 30.0
        if query_norm in target_norm:
            return 16.0
        if target_norm in query_norm:
            return 11.0
        return 0.0

    def _intent_penalty(self, input_intents: set[str], combined_text: str) -> float:
        if not input_intents:
            return 0.0
        combined_tokens = set(extract_tokens(combined_text))
        penalties = 0.0
        for intent in input_intents:
            if INTENT_TOKENS[intent].isdisjoint(combined_tokens):
                penalties += 2.2
        return penalties

    def _score(self, text: str, item: dict[str, Any]) -> Candidate:
        query_norm = normalize_text(text)
        input_tokens_raw = extract_tokens(text, remove_stopwords=False)
        input_tokens = extract_tokens(text, remove_stopwords=True)
        input_tokens_expanded = expand_tokens(input_tokens)
        input_intents = infer_intents(input_tokens_raw)
        hits: list[str] = []
        score = 0.0

        name = item["name"]
        name_norm = item["name_norm"]
        code = item["code"]

        score += self._text_match_score(query_norm, name_norm)
        if score > 0:
            hits.append(name)

        name_tokens = set(extract_tokens(name))
        add, token_hits = self._token_overlap_score(input_tokens, name_tokens, per_token=6.2)
        score += add
        hits.extend(token_hits)
        add_syn, syn_hits = self._token_overlap_score(input_tokens_expanded, name_tokens, per_token=2.3)
        score += add_syn
        hits.extend(syn_hits)

        notes = item.get("notes", [])
        include_notes = item.get("include_notes", [])
        exclude_notes = item.get("exclude_notes", [])
        example_notes = item.get("example_notes", [])

        note_hits: list[str] = []
        for note in notes:
            note_norm = normalize_text(note)
            if not note_norm:
                continue
            score += self._text_match_score(query_norm, note_norm) * 0.45
            note_tokens = set(extract_tokens(note))
            add_note, hits_note = self._token_overlap_score(input_tokens, note_tokens, per_token=2.4)
            score += add_note
            note_hits.extend(hits_note)
            add_note_syn, note_syn_hits = self._token_overlap_score(input_tokens_expanded, note_tokens, per_token=1.1)
            score += add_note_syn
            note_hits.extend(note_syn_hits)

        for note in include_notes:
            note_tokens = set(extract_tokens(note))
            add_inc, inc_hits = self._token_overlap_score(input_tokens, note_tokens, per_token=2.9)
            score += add_inc
            note_hits.extend(inc_hits)
            add_inc_syn, inc_syn_hits = self._token_overlap_score(input_tokens_expanded, note_tokens, per_token=1.2)
            score += add_inc_syn
            note_hits.extend(inc_syn_hits)

        for note in example_notes:
            note_tokens = set(extract_tokens(note))
            add_ex, ex_hits = self._token_overlap_score(input_tokens, note_tokens, per_token=2.6)
            score += add_ex
            note_hits.extend(ex_hits)
            add_ex_syn, ex_syn_hits = self._token_overlap_score(input_tokens_expanded, note_tokens, per_token=1.2)
            score += add_ex_syn
            note_hits.extend(ex_syn_hits)

        # 입력과 정확히 상충되는 제외 항목이 있는 경우 점수 감점
        query_token_set = set(input_tokens)
        for note in exclude_notes:
            excl_tokens = set(extract_tokens(note))
            overlap = query_token_set.intersection(excl_tokens)
            if overlap:
                score -= 1.8 * len(overlap)

        combined_text = " ".join([name] + notes + include_notes + example_notes)
        score -= self._intent_penalty(input_intents, combined_text)

        # 단일 영문 섹션 코드(A-U)는 구체성이 낮아서 약한 감점
        if re.fullmatch(r"[A-U]", code):
            score *= 0.86
        # 4~5자리 세분류 코드가 이름/노트와 충분히 매칭되면 소폭 가산
        if len(code) >= 4 and score >= 7:
            score += 0.7

        uniq_hits = sorted(set(hits + note_hits), key=lambda x: (-len(x), x))[:8]
        return Candidate(code=code, name=name, score=max(score, 0.0), matched_keywords=uniq_hits)

    def classify(self, text: str, top_k: int = 3) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {
                "code": "UNMATCHED",
                "name": "수동분류 필요",
                "confidence": 0.0,
                "matched_keywords": [],
                "candidates": [],
            }

        scored = [self._score(text, item) for item in self.items]
        scored.sort(key=lambda x: x.score, reverse=True)

        best = scored[0] if scored else None
        if not best or best.score <= 0:
            return {
                "code": "UNMATCHED",
                "name": "수동분류 필요",
                "confidence": 0.0,
                "matched_keywords": [],
                "candidates": [],
            }

        second_score = scored[1].score if len(scored) > 1 else 0.0
        confidence = (best.score - second_score) / (best.score + 1.0)
        confidence = max(0.0, min(1.0, confidence))

        return {
            "code": best.code,
            "name": best.name,
            "confidence": round(confidence, 3),
            "matched_keywords": best.matched_keywords,
            "candidates": [
                {"code": c.code, "name": c.name, "score": round(c.score, 3)}
                for c in scored[: max(top_k, 1)]
            ],
        }


def detect_input_column(fieldnames: list[str]) -> str | None:
    candidates = ["업종내역", "업종", "업종명", "사업내용", "종목", "업태", "text", "input"]
    lowered = {name.lower(): name for name in fieldnames}
    for col in candidates:
        if col in fieldnames:
            return col
        key = col.lower()
        if key in lowered:
            return lowered[key]
    return None


def classify_csv(matcher: IndustryCodeMatcher, input_csv: Path, output_csv: Path, column: str | None) -> None:
    with input_csv.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            raise ValueError("CSV header not found")

        input_col = column or detect_input_column(reader.fieldnames)
        if not input_col:
            raise ValueError(f"input column not found. headers={reader.fieldnames}")

        out_fields = list(reader.fieldnames) + [
            "매칭코드",
            "산업분류명",
            "신뢰도",
            "매칭키워드",
            "후보1",
            "후보2",
            "후보3",
        ]

        with output_csv.open("w", encoding="utf-8-sig", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=out_fields)
            writer.writeheader()
            for row in reader:
                text = str(row.get(input_col, "")).strip()
                result = matcher.classify(text)
                candidates = result["candidates"]
                row["매칭코드"] = result["code"]
                row["산업분류명"] = result["name"]
                row["신뢰도"] = f"{float(result['confidence']):.3f}"
                row["매칭키워드"] = ", ".join(result["matched_keywords"])
                row["후보1"] = f"{candidates[0]['code']}:{candidates[0]['name']}" if len(candidates) >= 1 else ""
                row["후보2"] = f"{candidates[1]['code']}:{candidates[1]['name']}" if len(candidates) >= 2 else ""
                row["후보3"] = f"{candidates[2]['code']}:{candidates[2]['name']}" if len(candidates) >= 3 else ""
                writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KSIC 산업분류 코드 매칭기")
    parser.add_argument("--index", default="ksic_index_full.json", help="KSIC 인덱스 JSON 경로")
    parser.add_argument("--text", help="단일 업종 텍스트")
    parser.add_argument("--csv", help="입력 CSV 경로")
    parser.add_argument("--out", help="출력 CSV 경로")
    parser.add_argument("--column", help="입력 CSV의 업종 텍스트 컬럼명")
    parser.add_argument("--top-k", type=int, default=3, help="후보 개수")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    matcher = IndustryCodeMatcher(args.index)

    if args.text:
        result = matcher.classify(args.text, top_k=args.top_k)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.csv:
        if not args.out:
            raise ValueError("--csv 사용 시 --out 필요")
        classify_csv(matcher, Path(args.csv), Path(args.out), args.column)
        print(f"완료: {args.out}")
        return

    raise ValueError("사용법: --text 또는 --csv/--out 중 하나를 지정하세요.")


if __name__ == "__main__":
    main()
