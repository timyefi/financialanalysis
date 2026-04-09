from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DUPLICATE_HASH_CSV = OUTPUT_DIR / "同公司重复PDF_按哈希确认.csv"
DOWNLOAD_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果.csv"
DUPLICATE_ARCHIVE_DIR = OUTPUT_DIR / "重复PDF_按哈希移出"
MOVE_LOG_CSV = OUTPUT_DIR / "哈希确认重复文件_移动结果.csv"
DEDUPED_DOWNLOAD_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果_去重后.csv"
DEDUPED_ACTIVE_LIST_CSV = OUTPUT_DIR / "2024年年报保留文件清单_去重后.csv"



def load_duplicate_candidates() -> pd.DataFrame:
    duplicate_df = pd.read_csv(DUPLICATE_HASH_CSV)
    duplicate_df["IS_DUPLICATE_TO_DELETE"] = duplicate_df["IS_DUPLICATE_TO_DELETE"].fillna(False).astype(bool)
    return duplicate_df.loc[duplicate_df["IS_DUPLICATE_TO_DELETE"]].copy()



def ensure_archive_path(file_name: str) -> Path:
    archive_path = DUPLICATE_ARCHIVE_DIR / file_name
    if not archive_path.exists():
        return archive_path

    stem = archive_path.stem
    suffix = archive_path.suffix
    counter = 2
    while True:
        candidate = archive_path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1



def move_duplicates(duplicate_candidates: pd.DataFrame) -> pd.DataFrame:
    DUPLICATE_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    move_records: list[dict[str, object]] = []

    for row in duplicate_candidates.itertuples(index=False):
        source_path = Path(str(row.FILE_PATH))
        archive_path = ensure_archive_path(str(row.FILE_NAME))
        moved = False
        note = ""

        if source_path.exists():
            shutil.move(str(source_path), str(archive_path))
            moved = True
            note = "moved_to_archive"
        else:
            note = "source_missing"

        move_records.append(
            {
                "COMPANY_NAME": row.COMPANY_NAME,
                "INFOTITLE": row.INFOTITLE,
                "ANNOUNCEMENTLINK": row.ANNOUNCEMENTLINK,
                "SHA256": row.SHA256,
                "KEEP_FILE": row.KEEP_FILE,
                "DUPLICATE_FILE": row.FILE_NAME,
                "SOURCE_FILE_PATH": str(source_path),
                "ARCHIVE_FILE_PATH": str(archive_path) if moved else "",
                "MOVED": moved,
                "NOTE": note,
            }
        )

    return pd.DataFrame(move_records)



def build_deduped_download_log(download_log: pd.DataFrame, move_log: pd.DataFrame) -> pd.DataFrame:
    deduped = download_log.copy()
    moved_map = move_log.set_index("ANNOUNCEMENTLINK").to_dict("index") if not move_log.empty else {}

    archive_statuses: list[str] = []
    archive_paths: list[str] = []
    archive_notes: list[str] = []

    for row in deduped.itertuples(index=False):
        moved_info = moved_map.get(str(row.ANNOUNCEMENTLINK))
        if moved_info and bool(moved_info["MOVED"]):
            archive_statuses.append("archived_duplicate")
            archive_paths.append(str(moved_info["ARCHIVE_FILE_PATH"]))
            archive_notes.append(f"duplicate_of:{moved_info['KEEP_FILE']}")
        elif moved_info:
            archive_statuses.append("duplicate_source_missing")
            archive_paths.append("")
            archive_notes.append(str(moved_info["NOTE"]))
        else:
            archive_statuses.append(str(row.STATUS))
            archive_paths.append(str(row.TARGET_FILE) if not pd.isna(row.TARGET_FILE) else "")
            archive_notes.append(str(row.ERROR) if not pd.isna(row.ERROR) else "")

    deduped["STATUS_AFTER_DEDUP"] = archive_statuses
    deduped["ACTIVE_FILE_PATH"] = archive_paths
    deduped["DEDUP_NOTE"] = archive_notes
    return deduped



def build_active_file_list(deduped_download_log: pd.DataFrame) -> pd.DataFrame:
    active = deduped_download_log.loc[
        deduped_download_log["STATUS_AFTER_DEDUP"] == "downloaded"
    ].copy()
    active = active[
        [
            "INFOPUBLDATE",
            "COMPANY_NAME",
            "INFOTITLE",
            "ANNOUNCEMENTLINK",
            "TARGET_FILE_NAME",
            "ACTIVE_FILE_PATH",
            "FILE_SIZE",
        ]
    ]
    active = active.sort_values(["COMPANY_NAME", "INFOPUBLDATE", "INFOTITLE"], kind="stable")
    return active



def main() -> None:
    duplicate_candidates = load_duplicate_candidates()
    download_log = pd.read_csv(DOWNLOAD_LOG_CSV)

    move_log = move_duplicates(duplicate_candidates)
    deduped_download_log = build_deduped_download_log(download_log, move_log)
    active_file_list = build_active_file_list(deduped_download_log)

    move_log.to_csv(MOVE_LOG_CSV, index=False, encoding="utf-8-sig")
    deduped_download_log.to_csv(DEDUPED_DOWNLOAD_LOG_CSV, index=False, encoding="utf-8-sig")
    active_file_list.to_csv(DEDUPED_ACTIVE_LIST_CSV, index=False, encoding="utf-8-sig")

    moved_count = int(move_log["MOVED"].sum()) if not move_log.empty else 0
    kept_count = int((deduped_download_log["STATUS_AFTER_DEDUP"] == "downloaded").sum())
    archived_count = int((deduped_download_log["STATUS_AFTER_DEDUP"] == "archived_duplicate").sum())
    failed_count = int((deduped_download_log["STATUS_AFTER_DEDUP"] == "failed").sum())

    print(f"已移动重复文件数: {moved_count}")
    print(f"保留活动文件数: {kept_count}")
    print(f"已归档重复记录数: {archived_count}")
    print(f"仍失败未下载记录数: {failed_count}")
    print(f"重复文件归档目录: {DUPLICATE_ARCHIVE_DIR}")
    print(f"重复文件移动日志: {MOVE_LOG_CSV}")
    print(f"去重后下载结果: {DEDUPED_DOWNLOAD_LOG_CSV}")
    print(f"去重后保留文件清单: {DEDUPED_ACTIVE_LIST_CSV}")


if __name__ == "__main__":
    main()
