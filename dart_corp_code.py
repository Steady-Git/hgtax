"""
DART OpenAPI - 고유번호(corp_code) 전체 목록을 받아 SQLite에 저장.

사용법:
    1) API_KEY 에 본인 인증키 입력
    2) python dart_corp_code.py
    3) 같은 폴더에 dart.db 생성됨

주기적 실행:
    DART는 회사 정보가 수시로 바뀌므로 주 1회 정도 재실행 권장.
    재실행 시 기존 데이터는 덮어쓰기(UPSERT)되고, 삭제된 회사는
    아래 prune=True 로직으로 정리할 수 있음.
"""

import io
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

API_KEY = "여기에_본인_API_KEY_입력"  # 예: "6079afb4a352faee1343813dbaea10848c55d8c7"
DB_PATH = Path("dart.db")
API_URL = "https://opendart.fss.or.kr/api/corpCode.xml"


def fetch_corp_code_xml(api_key: str) -> bytes:
    """DART에서 ZIP을 받아 안에 든 CORPCODE.xml 바이트를 반환."""
    resp = requests.get(API_URL, params={"crtfc_key": api_key}, timeout=30)
    resp.raise_for_status()

    # 응답이 ZIP이 아니라 에러 XML로 올 수도 있음 (잘못된 키 등)
    if not resp.content.startswith(b"PK"):
        # 에러 메시지 그대로 보여주기
        raise RuntimeError(f"ZIP이 아닌 응답 수신:\n{resp.text}")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("CORPCODE.xml") as f:
            return f.read()


def parse_corp_code(xml_bytes: bytes) -> list[dict]:
    """XML을 파싱해 dict 리스트로 변환."""
    root = ET.fromstring(xml_bytes)
    rows = []
    for item in root.iter("list"):
        rows.append({
            "corp_code":     (item.findtext("corp_code") or "").strip(),
            "corp_name":     (item.findtext("corp_name") or "").strip(),
            "corp_eng_name": (item.findtext("corp_eng_name") or "").strip(),
            "stock_code":    (item.findtext("stock_code") or "").strip() or None,
            "modify_date":   (item.findtext("modify_date") or "").strip(),
        })
    return rows


def init_db(conn: sqlite3.Connection) -> None:
    """테이블/인덱스 생성 (이미 있으면 무시)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS corp_code (
            corp_code     TEXT PRIMARY KEY,
            corp_name     TEXT NOT NULL,
            corp_eng_name TEXT,
            stock_code    TEXT,           -- 상장사만 값 있음(6자리), 아니면 NULL
            modify_date   TEXT,           -- YYYYMMDD
            updated_at    TEXT NOT NULL   -- 이 행을 마지막으로 갱신한 시각
        );

        CREATE INDEX IF NOT EXISTS idx_corp_name  ON corp_code(corp_name);
        CREATE INDEX IF NOT EXISTS idx_stock_code ON corp_code(stock_code);
    """)


def upsert_rows(conn: sqlite3.Connection, rows: list[dict], prune: bool = False) -> None:
    """rows를 UPSERT. prune=True면 이번에 없는 corp_code는 삭제."""
    now = datetime.now().isoformat(timespec="seconds")

    conn.execute("BEGIN")
    conn.executemany(
        """
        INSERT INTO corp_code
            (corp_code, corp_name, corp_eng_name, stock_code, modify_date, updated_at)
        VALUES
            (:corp_code, :corp_name, :corp_eng_name, :stock_code, :modify_date, :updated_at)
        ON CONFLICT(corp_code) DO UPDATE SET
            corp_name     = excluded.corp_name,
            corp_eng_name = excluded.corp_eng_name,
            stock_code    = excluded.stock_code,
            modify_date   = excluded.modify_date,
            updated_at    = excluded.updated_at
        """,
        [{**r, "updated_at": now} for r in rows],
    )

    if prune:
        # 이번 응답에 없는 corp_code는 삭제 (회사 폐지 등)
        codes = [(r["corp_code"],) for r in rows]
        conn.execute("CREATE TEMP TABLE _keep(corp_code TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO _keep VALUES (?)", codes)
        conn.execute("""
            DELETE FROM corp_code
            WHERE corp_code NOT IN (SELECT corp_code FROM _keep)
        """)
        conn.execute("DROP TABLE _keep")

    conn.commit()


def main():
    print("[1/3] DART에서 고유번호 ZIP 다운로드 중...")
    xml_bytes = fetch_corp_code_xml(API_KEY)

    print("[2/3] XML 파싱 중...")
    rows = parse_corp_code(xml_bytes)
    listed = sum(1 for r in rows if r["stock_code"])
    print(f"    총 {len(rows):,}개 회사 (상장사 {listed:,}개)")

    print(f"[3/3] {DB_PATH} 에 저장 중...")
    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        upsert_rows(conn, rows, prune=False)  # 첫 실행은 prune=False 권장

    print("완료.")


if __name__ == "__main__":
    main()
