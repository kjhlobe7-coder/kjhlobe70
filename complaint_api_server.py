#!/usr/bin/env python3
"""민원 소관 부서 분류 API 서버 (표준 라이브러리 기반)."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from complaint_department_classifier import ComplaintDepartmentClassifier


CLASSIFIER = ComplaintDepartmentClassifier()


class ComplaintHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/classify":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "empty request body"})
            return

        raw = self.rfile.read(content_length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})
            return

        complaint = str(data.get("text", "")).strip()
        if not complaint:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "'text' is required"})
            return

        result = CLASSIFIER.classify(complaint)
        self._send_json(
            HTTPStatus.OK,
            {
                "department": result.department,
                "confidence": result.confidence,
                "matched_keywords": result.matched_keywords,
                "candidates": result.candidates,
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        return


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), ComplaintHandler)
    print(f"민원 분류 API 서버 실행 중: http://{host}:{port}")
    print("POST /classify, GET /health")
    server.serve_forever()


if __name__ == "__main__":
    run()
