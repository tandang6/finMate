# test_kospi_last_n.py
from ecos import get_kospi_last_n

if __name__ == "__main__":
    print("=== get_kospi_last_n(6) 테스트 ===")
    rows = get_kospi_last_n(6)

    # 1) 에러 체크
    if isinstance(rows, dict) and "error" in rows:
        print("❌ ECOS 에러:", rows["error"])
    else:
        print("총 개수:", len(rows))
        for r in rows:
            time = r.get("TIME")
            value = r.get("DATA_VALUE")
            unit = r.get("UNIT_NAME")
            print(f"- {time}  =>  {value}  ({unit})")
