#!/usr/bin/env python3
"""통상임금 계산기

이 스크립트는 한국의 통상임금(기본급+통상적 수당)을 기준으로
일급과 시급을 계산하고, 선택적으로 초과근무 수당까지 계산합니다.
"""

from __future__ import annotations


def parse_float(prompt: str, default: float | None = None) -> float:
    while True:
        try:
            raw = input(prompt).strip()
            if raw == "" and default is not None:
                return default
            value = float(raw)
            if value < 0:
                raise ValueError("음수는 허용되지 않습니다.")
            return value
        except ValueError as exc:
            print(f"입력 오류: {exc}. 다시 시도해주세요.")


def calculate_ordinary_wage(
    monthly_base: float,
    regular_allowance: float,
    pay_days_per_month: float = 30,
    work_hours_per_day: float = 8,
) -> dict[str, float]:
    total_ordinary = monthly_base + regular_allowance
    daily_ordinary = total_ordinary / pay_days_per_month if pay_days_per_month else 0.0
    hourly_ordinary = daily_ordinary / work_hours_per_day if work_hours_per_day else 0.0
    return {
        "monthly_ordinary_wage": total_ordinary,
        "daily_ordinary_wage": daily_ordinary,
        "hourly_ordinary_wage": hourly_ordinary,
    }


def calculate_overtime_pay(hourly_wage: float, overtime_hours: float, overtime_rate: float = 1.5) -> float:
    return hourly_wage * overtime_hours * overtime_rate


def main() -> None:
    print("=== 통상임금 계산기 ===")
    print("입력값은 음수가 될 수 없습니다. 그냥 Enter를 누르면 기본값이 사용됩니다.")

    monthly_base = parse_float("기본급(월) 입력: ")
    regular_allowance = parse_float("통상적 수당(월) 입력 (예: 정기 상여금 제외): ")
    pay_days_per_month = parse_float("월 유급 기준 일수 입력 (기본 30): ", default=30)
    work_hours_per_day = parse_float("하루 근무시간 입력 (기본 8): ", default=8)

    results = calculate_ordinary_wage(
        monthly_base=monthly_base,
        regular_allowance=regular_allowance,
        pay_days_per_month=pay_days_per_month,
        work_hours_per_day=work_hours_per_day,
    )

    print("\n--- 통상임금 계산 결과 ---")
    print(f"월 통상임금: {results['monthly_ordinary_wage']:.2f} 원")
    print(f"일 통상임금: {results['daily_ordinary_wage']:.2f} 원")
    print(f"시 통상임금: {results['hourly_ordinary_wage']:.2f} 원")

    overtime_hours = parse_float("초과근무 시간 입력 (없으면 0): ", default=0)
    if overtime_hours > 0:
        overtime_rate = parse_float("가산율 입력 (기본 1.5배면 1.5): ", default=1.5)
        overtime_pay = calculate_overtime_pay(results["hourly_ordinary_wage"], overtime_hours, overtime_rate)
        print(f"초과근무 수당: {overtime_pay:.2f} 원")

    print("==========================")


if __name__ == "__main__":
    main()
