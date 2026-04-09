from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DOWNLOAD_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果.csv"
DUPLICATE_HASH_CSV = OUTPUT_DIR / "同公司重复PDF_按哈希确认.csv"
SAME_SIZE_DIFF_HASH_CSV = OUTPUT_DIR / "同公司同大小但不同哈希_待人工复核.csv"
GLOBAL_COMMON_FILES_CSV = OUTPUT_DIR / "全局高频重复文件特征.csv"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()



def load_downloaded_files() -> pd.DataFrame:
    log_df = pd.read_csv(DOWNLOAD_LOG_CSV)
    downloaded = log_df.loc[log_df["STATUS"] == "downloaded"].copy()
    downloaded["FILE_PATH"] = downloaded["TARGET_FILE"].astype(str)
    downloaded["FILE_NAME"] = downloaded["FILE_PATH"].map(lambda value: Path(value).name)
    downloaded["FILE_SIZE"] = pd.to_numeric(downloaded["FILE_SIZE"], errors="coerce")
    downloaded = downloaded[downloaded["FILE_PATH"] != ""].copy()
    downloaded["FILE_EXISTS"] = downloaded["FILE_PATH"].map(lambda value: Path(value).exists())
    downloaded = downloaded[downloaded["FILE_EXISTS"]].copy()
    downloaded["SHA256"] = downloaded["FILE_PATH"].map(lambda value: sha256_file(Path(value)))
    return downloaded



def build_hash_duplicates(downloaded: pd.DataFrame) -> pd.DataFrame:
    duplicated = downloaded[downloaded.duplicated(["COMPANY_NAME", "SHA256"], keep=False)].copy()
    if duplicated.empty:
        return duplicated

    duplicated["KEEP_FILE"] = duplicated.groupby(["COMPANY_NAME", "SHA256"])["FILE_NAME"].transform("min")
    duplicated["IS_DUPLICATE_TO_DELETE"] = duplicated["FILE_NAME"] != duplicated["KEEP_FILE"]
    duplicated = duplicated.sort_values(["COMPANY_NAME", "SHA256", "FILE_NAME"], kind="stable")
    return duplicated[
        [
            "COMPANY_NAME",
            "INFOTITLE",
            "ANNOUNCEMENTLINK",
            "FILE_NAME",
            "FILE_SIZE",
            "SHA256",
            "KEEP_FILE",
            "IS_DUPLICATE_TO_DELETE",
            "FILE_PATH",
        ]
    ]



def build_same_size_diff_hash(downloaded: pd.DataFrame) -> pd.DataFrame:
    grouped = downloaded.groupby(["COMPANY_NAME", "FILE_SIZE"]).agg(
        FILE_COUNT=("FILE_NAME", "size"),
        HASH_COUNT=("SHA256", "nunique"),
    )
    suspicious_keys = grouped[(grouped["FILE_COUNT"] > 1) & (grouped["HASH_COUNT"] > 1)].reset_index()[
        ["COMPANY_NAME", "FILE_SIZE"]
    ]
    if suspicious_keys.empty:
        return pd.DataFrame()

    suspicious = downloaded.merge(suspicious_keys, on=["COMPANY_NAME", "FILE_SIZE"], how="inner")
    suspicious = suspicious.sort_values(["COMPANY_NAME", "FILE_SIZE", "FILE_NAME"], kind="stable")
    return suspicious[
        [
            "COMPANY_NAME",
            "INFOTITLE",
            "ANNOUNCEMENTLINK",
            "FILE_NAME",
            "FILE_SIZE",
            "SHA256",
            "FILE_PATH",
        ]
    ]



def build_global_common_files(downloaded: pd.DataFrame) -> pd.DataFrame:
    grouped = downloaded.groupby(["FILE_SIZE", "SHA256"]).agg(
        FILE_COUNT=("FILE_NAME", "size"),
        COMPANY_COUNT=("COMPANY_NAME", "nunique"),
        SAMPLE_COMPANIES=("COMPANY_NAME", lambda values: " | ".join(sorted(pd.unique(values))[:10])),
        SAMPLE_FILES=("FILE_NAME", lambda values: " | ".join(list(values)[:10])),
    )
    grouped = grouped.sort_values(["FILE_COUNT", "COMPANY_COUNT"], ascending=[False, False]).reset_index()
    return grouped



def main() -> None:
    downloaded = load_downloaded_files()

    hash_duplicates = build_hash_duplicates(downloaded)
    suspicious_same_size = build_same_size_diff_hash(downloaded)
    global_common = build_global_common_files(downloaded)

    hash_duplicates.to_csv(DUPLICATE_HASH_CSV, index=False, encoding="utf-8-sig")
    suspicious_same_size.to_csv(SAME_SIZE_DIFF_HASH_CSV, index=False, encoding="utf-8-sig")
    global_common.to_csv(GLOBAL_COMMON_FILES_CSV, index=False, encoding="utf-8-sig")

    duplicate_groups = 0
    duplicate_files = 0
    if not hash_duplicates.empty:
        duplicate_groups = int(hash_duplicates[["COMPANY_NAME", "SHA256"]].drop_duplicates().shape[0])
        duplicate_files = int(hash_duplicates.shape[0])

    delete_candidates = 0
    if not hash_duplicates.empty:
        delete_candidates = int(hash_duplicates["IS_DUPLICATE_TO_DELETE"].sum())

    print(f"已分析下载成功文件数: {len(downloaded)}")
    print(f"同公司且哈希完全一致的重复组数: {duplicate_groups}")
    print(f"落入重复组的文件数: {duplicate_files}")
    print(f"建议删除的重复文件数: {delete_candidates}")
    print(f"同公司同大小但哈希不同的待复核文件数: {len(suspicious_same_size)}")
    print(f"哈希确认重复清单: {DUPLICATE_HASH_CSV}")
    print(f"同大小不同哈希清单: {SAME_SIZE_DIFF_HASH_CSV}")
    print(f"全局高频重复特征: {GLOBAL_COMMON_FILES_CSV}")

    if not global_common.empty:
        print("\n全局最常见重复文件特征（前10条）:")
        print(global_common.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
