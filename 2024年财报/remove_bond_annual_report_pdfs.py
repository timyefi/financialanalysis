from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DEDUPED_DOWNLOAD_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果_去重后.csv"
REMOVAL_LOG_CSV = OUTPUT_DIR / "债券年度报告PDF_删除结果.csv"
UPDATED_DOWNLOAD_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果_去重并剔除债券年度报告后.csv"
UPDATED_KEEP_LIST_CSV = OUTPUT_DIR / "2024年年报保留文件清单_去重并剔除债券年度报告后.csv"
TITLE_PATTERN = r"债券年度报告|公司债券年度报告"



def is_target_title(title: object) -> bool:
    return pd.notna(title) and bool(pd.Series([str(title)]).str.contains(TITLE_PATTERN, na=False).iloc[0])



def normalize_existing_status(current_status: str, current_path: str, current_note: str) -> tuple[str, str, str]:
    if not current_path:
        return current_status, "", current_note

    file_path = Path(current_path)
    if file_path.exists() and file_path.is_file():
        return current_status, current_path, current_note

    if current_status == "archived_duplicate":
        return "archived_duplicate_missing", "", "file_missing_on_disk"
    if current_status == "downloaded":
        return "downloaded_file_missing", "", "file_missing_on_disk"
    return current_status, "", current_note



def remove_target_files(deduped_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    removal_records: list[dict[str, object]] = []
    updated_df = deduped_df.copy()

    statuses_after_removal: list[str] = []
    file_paths_after_removal: list[str] = []
    notes_after_removal: list[str] = []

    for row in updated_df.itertuples(index=False):
        current_status = str(row.STATUS_AFTER_DEDUP) if pd.notna(row.STATUS_AFTER_DEDUP) else ""
        current_path = str(row.ACTIVE_FILE_PATH) if pd.notna(row.ACTIVE_FILE_PATH) else ""
        current_note = str(row.DEDUP_NOTE) if pd.notna(row.DEDUP_NOTE) else ""

        if is_target_title(row.INFOTITLE) and current_path:
            target_path = Path(current_path)
            existed_before = target_path.exists() and target_path.is_file()
            deleted = False
            note = "target_missing"

            if existed_before:
                target_path.unlink()
                deleted = True
                note = "deleted"
            elif target_path.exists() and not target_path.is_file():
                note = "not_a_file_path"

            removal_records.append(
                {
                    "INFOPUBLDATE": row.INFOPUBLDATE,
                    "COMPANY_NAME": row.COMPANY_NAME,
                    "INFOTITLE": row.INFOTITLE,
                    "ANNOUNCEMENTLINK": row.ANNOUNCEMENTLINK,
                    "STATUS_BEFORE": current_status,
                    "FILE_PATH": current_path,
                    "EXISTED_BEFORE_DELETE": existed_before,
                    "DELETED": deleted,
                    "NOTE": note,
                }
            )

            statuses_after_removal.append("removed_bond_annual_report")
            file_paths_after_removal.append("")
            notes_after_removal.append(note)
        else:
            normalized_status, normalized_path, normalized_note = normalize_existing_status(
                current_status,
                current_path,
                current_note,
            )
            statuses_after_removal.append(normalized_status)
            file_paths_after_removal.append(normalized_path)
            notes_after_removal.append(normalized_note)

    updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] = statuses_after_removal
    updated_df["ACTIVE_FILE_PATH_AFTER_BOND_REPORT_REMOVAL"] = file_paths_after_removal
    updated_df["BOND_REPORT_REMOVAL_NOTE"] = notes_after_removal

    removal_df = pd.DataFrame(removal_records)
    return updated_df, removal_df



def build_updated_keep_list(updated_df: pd.DataFrame) -> pd.DataFrame:
    kept = updated_df.loc[
        updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "downloaded"
    ].copy()
    kept = kept[
        [
            "INFOPUBLDATE",
            "COMPANY_NAME",
            "INFOTITLE",
            "ANNOUNCEMENTLINK",
            "TARGET_FILE_NAME",
            "ACTIVE_FILE_PATH_AFTER_BOND_REPORT_REMOVAL",
            "FILE_SIZE",
        ]
    ]
    kept = kept.rename(columns={"ACTIVE_FILE_PATH_AFTER_BOND_REPORT_REMOVAL": "ACTIVE_FILE_PATH"})
    kept = kept.sort_values(["COMPANY_NAME", "INFOPUBLDATE", "INFOTITLE"], kind="stable")
    return kept



def main() -> None:
    deduped_df = pd.read_csv(DEDUPED_DOWNLOAD_LOG_CSV)
    updated_df, removal_df = remove_target_files(deduped_df)
    keep_df = build_updated_keep_list(updated_df)

    removal_df.to_csv(REMOVAL_LOG_CSV, index=False, encoding="utf-8-sig")
    updated_df.to_csv(UPDATED_DOWNLOAD_LOG_CSV, index=False, encoding="utf-8-sig")
    keep_df.to_csv(UPDATED_KEEP_LIST_CSV, index=False, encoding="utf-8-sig")

    removed_count = int((updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "removed_bond_annual_report").sum())
    kept_count = int((updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "downloaded").sum())
    archived_count = int((updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "archived_duplicate").sum())
    archived_missing_count = int((updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "archived_duplicate_missing").sum())
    failed_count = int((updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "failed").sum())
    downloaded_missing_count = int((updated_df["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "downloaded_file_missing").sum())

    print(f"已删除债券年度报告PDF记录数: {removed_count}")
    print(f"删除后保留活动文件数: {kept_count}")
    print(f"删除后仍为已归档重复记录数: {archived_count}")
    print(f"删除后发现已缺失的归档重复记录数: {archived_missing_count}")
    print(f"删除后仍失败未下载记录数: {failed_count}")
    print(f"删除后发现已缺失的活动文件记录数: {downloaded_missing_count}")
    print(f"删除日志: {REMOVAL_LOG_CSV}")
    print(f"更新后的完整结果: {UPDATED_DOWNLOAD_LOG_CSV}")
    print(f"更新后的保留文件清单: {UPDATED_KEEP_LIST_CSV}")


if __name__ == "__main__":
    main()
