from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

SOURCE_CSV = Path(r"C:\Users\Administrator\Downloads\债券公告非文本\债券公告非文本.csv")
START_DATE = pd.Timestamp("2025-04-01")
END_DATE = pd.Timestamp("2025-08-31 23:59:59")
CHUNK_SIZE = 200_000
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
CANDIDATE_CSV = OUTPUT_DIR / "2025-04-01_2025-08-31_年报候选子集.csv"
FINAL_CSV = OUTPUT_DIR / "2024年年报链接清单.csv"
DOWNLOAD_DIR = OUTPUT_DIR / "2024年年报PDF"
DOWNLOAD_LOG_CSV = OUTPUT_DIR / "2024年年报下载结果.csv"
MAX_WORKERS = 32
REQUEST_TIMEOUT = (10, 45)

INITIAL_KEYWORDS_PATTERN = re.compile(r"财报|年报|年度报告|财务报告")
NEGATIVE_PATTERN = re.compile(
    r"一季度|二季度|三季度|四季度|半年度|中期|季度|季报|9月末|1-9月|"
    r"摘要|公告|通知|说明|更正|更正版|补充|链接|披露工作|风险提示|延期披露|无法按(?:时|期)披露|"
    r"受托|受托人|受托机构|受托管理|临时受托管理事务报告|专项报告|存续期披露材料|"
    r"募集资金使用情况|英文版本|简体中文|繁体中文",
)
ANNUAL_POSITIVE_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"2024年年度报告",
        r"2024年度报告",
        r"2024年年报",
        r"公司债券年度报告[（(]2024年[）)]",
        r"公司债券2024年年度报告",
        r"2024年年度财务报告及附注",
        r"2024年度财务报告及附注",
        r"2024年经审计的财务报告",
        r"经审计的2024年度财务报告",
        r"2024年度经审计财务报告",
        r"2024年度经审计的合并财务报告",
        r"2024年度经审计的合并及母公司财务报告",
        r"2024年度经审计的财务报告及母公司会计报表",
        r"2024年度报告及审计报告",
    ]
]
COMPANY_EXTRACTION_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"^(?P<company>.+?)公司债券年度报告[（(]2024年[）)]",
        r"^(?P<company>.+?)公司债券2024年年度报告",
        r"^(?P<company>.+?)2024年年度报告",
        r"^(?P<company>.+?)2024年度年度报告",
        r"^(?P<company>.+?)2024年度报告",
        r"^(?P<company>.+?)2024年年报",
        r"^(?P<company>.+?)2024年年度财务报告及附注",
        r"^(?P<company>.+?)2024年度财务报告及附注",
        r"^(?P<company>.+?)2024年经审计的财务报告",
        r"^(?P<company>.+?)经审计的2024年度财务报告",
        r"^(?P<company>.+?)2024年度经审计财务报告",
        r"^(?P<company>.+?)2024年度经审计的合并财务报告",
        r"^(?P<company>.+?)2024年度经审计的合并及母公司财务报告",
        r"^(?P<company>.+?)2024年度经审计的财务报告及母公司会计报表",
        r"^(?P<company>.+?)2024年度报告及审计报告",
    ]
]
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def normalize_title(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = re.sub(r"\s+", "", text)
    return text.replace("（", "(").replace("）", ")")



def build_candidate_subset(source_csv: Path, candidate_csv: Path) -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chunks: list[pd.DataFrame] = []
    usecols = ["INFOPUBLDATE", "INFOTITLE", "ANNOUNCEMENTLINK"]

    for chunk in pd.read_csv(source_csv, usecols=usecols, chunksize=CHUNK_SIZE):
        chunk["INFOPUBLDATE"] = pd.to_datetime(chunk["INFOPUBLDATE"], errors="coerce")
        chunk["INFOTITLE"] = chunk["INFOTITLE"].fillna("")
        chunk["TITLE_NORMALIZED"] = chunk["INFOTITLE"].map(normalize_title)

        mask = (
            chunk["INFOPUBLDATE"].between(START_DATE, END_DATE)
            & chunk["TITLE_NORMALIZED"].str.contains(INITIAL_KEYWORDS_PATTERN, na=False)
        )
        filtered = chunk.loc[mask, ["INFOPUBLDATE", "INFOTITLE", "ANNOUNCEMENTLINK", "TITLE_NORMALIZED"]]
        if not filtered.empty:
            chunks.append(filtered)

    if chunks:
        candidates = pd.concat(chunks, ignore_index=True)
        candidates = candidates.drop_duplicates(subset=["INFOPUBLDATE", "INFOTITLE", "ANNOUNCEMENTLINK"])
    else:
        candidates = pd.DataFrame(columns=["INFOPUBLDATE", "INFOTITLE", "ANNOUNCEMENTLINK", "TITLE_NORMALIZED"])

    candidates.to_csv(candidate_csv, index=False, encoding="utf-8-sig")
    return candidates



def load_or_build_candidates(source_csv: Path, candidate_csv: Path) -> pd.DataFrame:
    if candidate_csv.exists():
        candidates = pd.read_csv(candidate_csv)
        if "TITLE_NORMALIZED" not in candidates.columns:
            candidates["TITLE_NORMALIZED"] = candidates["INFOTITLE"].map(normalize_title)
        candidates["INFOPUBLDATE"] = pd.to_datetime(candidates["INFOPUBLDATE"], errors="coerce")
        return candidates
    return build_candidate_subset(source_csv, candidate_csv)



def is_2024_annual_report(title_normalized: str) -> bool:
    if "2024" not in title_normalized:
        return False
    if NEGATIVE_PATTERN.search(title_normalized):
        return False
    return any(pattern.search(title_normalized) for pattern in ANNUAL_POSITIVE_PATTERNS)



def extract_company_name(title_normalized: str) -> str:
    for pattern in COMPANY_EXTRACTION_PATTERNS:
        matched = pattern.search(title_normalized)
        if matched:
            return matched.group("company")

    company = title_normalized.split("2024", 1)[0]
    company = re.sub(r"(公司债券|年度报告|年报|财务报告及附注|经审计的|财务报告)+$", "", company)
    return company or "未识别公司"



def sanitize_filename(name: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", name).strip(" .")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned or "未命名文件"



def build_target_file_name(company_name: str, announcement_link: str) -> str:
    link_hash = hashlib.md5(announcement_link.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    return sanitize_filename(f"{company_name}_2024年年报_{link_hash}.pdf")



def prepare_final_subset(candidates: pd.DataFrame) -> pd.DataFrame:
    filtered = candidates.loc[candidates["TITLE_NORMALIZED"].map(is_2024_annual_report)].copy()
    filtered = filtered.drop_duplicates(subset=["ANNOUNCEMENTLINK"])
    filtered["COMPANY_NAME"] = filtered["TITLE_NORMALIZED"].map(extract_company_name)
    filtered["TARGET_FILE_NAME"] = filtered.apply(
        lambda row: build_target_file_name(str(row["COMPANY_NAME"]), str(row["ANNOUNCEMENTLINK"])),
        axis=1,
    )
    filtered = filtered.sort_values(["INFOPUBLDATE", "COMPANY_NAME", "INFOTITLE"], kind="stable").reset_index(drop=True)
    return filtered



def load_existing_download_log(log_csv: Path) -> pd.DataFrame:
    if not log_csv.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(log_csv)
    except (OSError, ValueError, pd.errors.EmptyDataError):  # noqa: BLE001
        return pd.DataFrame()



def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
            "Accept": "application/pdf,application/octet-stream,*/*",
        }
    )
    return session



def is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code not in {403, 404, 421}
    return True



def download_one(row_dict: dict[str, object], download_dir: Path) -> dict[str, object]:
    url = str(row_dict["ANNOUNCEMENTLINK"])
    file_path = download_dir / str(row_dict["TARGET_FILE_NAME"])
    status = "failed"
    error_message = ""
    file_size: int | None = None

    if file_path.exists() and file_path.stat().st_size > 0:
        return {
            **row_dict,
            "TARGET_FILE": str(file_path),
            "STATUS": "downloaded",
            "FILE_SIZE": file_path.stat().st_size,
            "ERROR": "",
        }

    session = create_session()

    for attempt in range(1, 4):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True)
            response.raise_for_status()
            with open(file_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        handle.write(chunk)
            file_size = file_path.stat().st_size
            if file_size == 0:
                raise ValueError("下载结果为空文件")
            status = "downloaded"
            error_message = ""
            break
        except (requests.RequestException, OSError, ValueError) as exc:  # noqa: BLE001
            error_message = f"attempt {attempt}: {exc}"
            if file_path.exists() and file_path.stat().st_size == 0:
                file_path.unlink(missing_ok=True)
            if not is_retryable_exception(exc):
                break

    if status != "downloaded":
        file_path = Path("")

    return {
        **row_dict,
        "TARGET_FILE": str(file_path) if file_path else "",
        "STATUS": status,
        "FILE_SIZE": file_size,
        "ERROR": error_message,
    }



def download_reports(final_df: pd.DataFrame, download_dir: Path, log_csv: Path) -> pd.DataFrame:
    download_dir.mkdir(parents=True, exist_ok=True)
    existing_log = load_existing_download_log(log_csv)
    successful_urls: set[str] = set()

    if not existing_log.empty and {"ANNOUNCEMENTLINK", "STATUS"}.issubset(existing_log.columns):
        successful_urls = set(
            existing_log.loc[existing_log["STATUS"] == "downloaded", "ANNOUNCEMENTLINK"].astype(str)
        )

    base_records = final_df.to_dict("records")
    pending_rows: list[dict[str, object]] = []
    completed_records: list[dict[str, object]] = []

    for row_dict in base_records:
        url = str(row_dict["ANNOUNCEMENTLINK"])
        file_path = download_dir / str(row_dict["TARGET_FILE_NAME"])
        if url in successful_urls and file_path.exists() and file_path.stat().st_size > 0:
            completed_records.append(
                {
                    **row_dict,
                    "TARGET_FILE": str(file_path),
                    "STATUS": "downloaded",
                    "FILE_SIZE": file_path.stat().st_size,
                    "ERROR": "",
                }
            )
        else:
            pending_rows.append(row_dict)

    if pending_rows:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(download_one, row_dict, download_dir) for row_dict in pending_rows]
            for index, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                completed_records.append(result)
                if index % 200 == 0 or index == len(pending_rows):
                    download_log = pd.DataFrame(completed_records)
                    download_log.to_csv(log_csv, index=False, encoding="utf-8-sig")
                    downloaded_count = int((download_log["STATUS"] == "downloaded").sum())
                    failed_count = int((download_log["STATUS"] != "downloaded").sum())
                    print(f"下载进度: {index}/{len(pending_rows)} | 成功 {downloaded_count} | 失败 {failed_count}", flush=True)

    download_log = pd.DataFrame(completed_records)
    download_log.to_csv(log_csv, index=False, encoding="utf-8-sig")
    return download_log



def main() -> None:
    if not SOURCE_CSV.exists():
        raise FileNotFoundError(f"未找到源文件: {SOURCE_CSV}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = load_or_build_candidates(SOURCE_CSV, CANDIDATE_CSV)
    final_df = prepare_final_subset(candidates)
    final_df.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
    download_log = download_reports(final_df, DOWNLOAD_DIR, DOWNLOAD_LOG_CSV)

    downloaded_count = int((download_log["STATUS"] == "downloaded").sum())
    failed_count = int((download_log["STATUS"] != "downloaded").sum())

    print(f"候选子集已保存: {CANDIDATE_CSV}")
    print(f"最终链接清单已保存: {FINAL_CSV}")
    print(f"PDF 下载目录: {DOWNLOAD_DIR}")
    print(f"下载日志已保存: {DOWNLOAD_LOG_CSV}")
    print(f"候选记录数: {len(candidates)}")
    print(f"最终年报记录数: {len(final_df)}")
    print(f"下载成功: {downloaded_count}")
    print(f"下载失败: {failed_count}")


if __name__ == "__main__":
    main()
