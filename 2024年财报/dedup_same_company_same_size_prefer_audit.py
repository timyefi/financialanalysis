from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
SOURCE_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果_去重并剔除债券年度报告后.csv"
REMOVAL_LOG_CSV = OUTPUT_DIR / "同公司同大小去重_删除结果.csv"
UPDATED_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果_最终去重后.csv"
UPDATED_KEEP_LIST_CSV = OUTPUT_DIR / "2024年年报保留文件清单_最终去重后.csv"
AUDIT_PATTERN = r"审计报告|经审计|审计的"



def is_audit_title(title: object) -> bool:
    return pd.notna(title) and bool(pd.Series([str(title)]).str.contains(AUDIT_PATTERN, na=False).iloc[0])



def choose_keeper(group: pd.DataFrame) -> pd.Series:
    ranked = group.copy()
    ranked["AUDIT_PRIORITY"] = ranked["INFOTITLE"].map(is_audit_title).map(lambda value: 0 if value else 1)
    ranked["INFOPUBLDATE"] = pd.to_datetime(ranked["INFOPUBLDATE"], errors="coerce")
    ranked = ranked.sort_values(
        ["AUDIT_PRIORITY", "INFOPUBLDATE", "INFOTITLE", "TARGET_FILE_NAME"],
        ascending=[True, True, True, True],
        kind="stable",
    )
    return ranked.iloc[0]



def deduplicate(downloaded_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = downloaded_df.copy()
    working["FILE_SIZE"] = pd.to_numeric(working["FILE_SIZE"], errors="coerce")

    active_mask = working["STATUS_AFTER_BOND_REPORT_REMOVAL"] == "downloaded"
    active = working.loc[active_mask].copy()

    grouped = active.groupby(["COMPANY_NAME", "FILE_SIZE"], dropna=False)
    removal_records: list[dict[str, object]] = []

    for (_, _), group in grouped:
        if len(group) <= 1:
            continue

        keeper = choose_keeper(group)
        keeper_link = str(keeper["ANNOUNCEMENTLINK"])
        keeper_file = str(keeper["TARGET_FILE_NAME"])
        keeper_title = str(keeper["INFOTITLE"])

        for row in group.itertuples(index=False):
            if str(row.ANNOUNCEMENTLINK) == keeper_link:
                continue

            file_path_str = str(row.ACTIVE_FILE_PATH_AFTER_BOND_REPORT_REMOVAL) if pd.notna(row.ACTIVE_FILE_PATH_AFTER_BOND_REPORT_REMOVAL) else ""
            file_path = Path(file_path_str) if file_path_str else None
            existed_before = bool(file_path and file_path.exists() and file_path.is_file())
            deleted = False
            note = "file_missing"

            if existed_before and file_path is not None:
                file_path.unlink()
                deleted = True
                note = "deleted"

            removal_records.append(
                {
                    "COMPANY_NAME": row.COMPANY_NAME,
                    "FILE_SIZE": row.FILE_SIZE,
                    "KEPT_INFOTITLE": keeper_title,
                    "KEPT_FILE": keeper_file,
                    "KEPT_ANNOUNCEMENTLINK": keeper_link,
                    "REMOVED_INFOTITLE": row.INFOTITLE,
                    "REMOVED_FILE": row.TARGET_FILE_NAME,
                    "REMOVED_ANNOUNCEMENTLINK": row.ANNOUNCEMENTLINK,
                    "REMOVED_FILE_PATH": file_path_str,
                    "EXISTED_BEFORE_DELETE": existed_before,
                    "DELETED": deleted,
                    "NOTE": note,
                    "KEEP_IS_AUDIT_REPORT": is_audit_title(keeper_title),
                }
            )

            row_mask = working["ANNOUNCEMENTLINK"].astype(str) == str(row.ANNOUNCEMENTLINK)
            working.loc[row_mask, "STATUS_FINAL"] = "removed_same_company_same_size_duplicate"
            working.loc[row_mask, "ACTIVE_FILE_PATH_FINAL"] = ""
            working.loc[row_mask, "FINAL_NOTE"] = f"same_company_same_size_keep:{keeper_file}"

        keeper_mask = working["ANNOUNCEMENTLINK"].astype(str) == keeper_link
        working.loc[keeper_mask, "STATUS_FINAL"] = "downloaded"
        working.loc[keeper_mask, "ACTIVE_FILE_PATH_FINAL"] = working.loc[keeper_mask, "ACTIVE_FILE_PATH_AFTER_BOND_REPORT_REMOVAL"]
        working.loc[keeper_mask, "FINAL_NOTE"] = working.loc[keeper_mask, "BOND_REPORT_REMOVAL_NOTE"]

    untouched_mask = working["STATUS_FINAL"].isna()
    working.loc[untouched_mask, "STATUS_FINAL"] = working.loc[untouched_mask, "STATUS_AFTER_BOND_REPORT_REMOVAL"]
    working.loc[untouched_mask, "ACTIVE_FILE_PATH_FINAL"] = working.loc[untouched_mask, "ACTIVE_FILE_PATH_AFTER_BOND_REPORT_REMOVAL"]
    working.loc[untouched_mask, "FINAL_NOTE"] = working.loc[untouched_mask, "BOND_REPORT_REMOVAL_NOTE"]

    removal_df = pd.DataFrame(removal_records)
    return working, removal_df



def build_keep_list(final_df: pd.DataFrame) -> pd.DataFrame:
    keep = final_df.loc[final_df["STATUS_FINAL"] == "downloaded"].copy()
    keep = keep[
        [
            "INFOPUBLDATE",
            "COMPANY_NAME",
            "INFOTITLE",
            "ANNOUNCEMENTLINK",
            "TARGET_FILE_NAME",
            "ACTIVE_FILE_PATH_FINAL",
            "FILE_SIZE",
        ]
    ]
    keep = keep.rename(columns={"ACTIVE_FILE_PATH_FINAL": "ACTIVE_FILE_PATH"})
    keep = keep.sort_values(["COMPANY_NAME", "INFOPUBLDATE", "INFOTITLE"], kind="stable")
    return keep



def main() -> None:
    df = pd.read_csv(SOURCE_LOG_CSV)
    final_df, removal_df = deduplicate(df)
    keep_df = build_keep_list(final_df)

    removal_df.to_csv(REMOVAL_LOG_CSV, index=False, encoding="utf-8-sig")
    final_df.to_csv(UPDATED_LOG_CSV, index=False, encoding="utf-8-sig")
    keep_df.to_csv(UPDATED_KEEP_LIST_CSV, index=False, encoding="utf-8-sig")

    removed_count = int((final_df["STATUS_FINAL"] == "removed_same_company_same_size_duplicate").sum())
    kept_count = int((final_df["STATUS_FINAL"] == "downloaded").sum())
    bond_removed_count = int((final_df["STATUS_FINAL"] == "removed_bond_annual_report").sum())
    failed_count = int((final_df["STATUS_FINAL"] == "failed").sum())
    archived_missing_count = int((final_df["STATUS_FINAL"] == "archived_duplicate_missing").sum())

    print(f"同公司同大小额外删除文件数: {removed_count}")
    print(f"最终保留活动文件数: {kept_count}")
    print(f"此前已剔除债券年度报告记录数: {bond_removed_count}")
    print(f"仍失败未下载记录数: {failed_count}")
    print(f"已缺失的归档重复记录数: {archived_missing_count}")
    print(f"删除日志: {REMOVAL_LOG_CSV}")
    print(f"最终完整结果: {UPDATED_LOG_CSV}")
    print(f"最终保留文件清单: {UPDATED_KEEP_LIST_CSV}")


if __name__ == "__main__":
    main()
