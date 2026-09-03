"""Safe, human-readable inspection and import for partner health-data packages."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID
from zipfile import BadZipFile, ZipFile

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.integrations.codes import canonical_code
from executive_health_ai.integrations.normalization import normalize_unit
from executive_health_ai.integrations.service import ingest
from executive_health_ai.models import ExternalIdentity, IngestionJob, KnowledgeChunk, KnowledgeDocument, Patient


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_FILES = 20
MAX_RECORDS = 25_000
MAX_JSON_DEPTH = 12
MAX_CELL_CHARS = 4_000
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".json", ".zip"}
PACKAGE_SCHEMA_VERSION = "1.0"

FIELD_ALIASES = {
    "external_member_id": {"外部成员编号", "成员编号", "external_member_id", "member_code", "member"},
    "metric": {"指标名称", "指标", "metric", "metric_name", "observation"},
    "value": {"数值", "值", "value", "result"},
    "unit": {"单位", "unit"},
    "observed_at": {"采集时间", "测量时间", "observed_at", "timestamp", "time"},
    "source": {"数据来源", "来源", "source"},
}

TYPE_FIELD_HINTS = {
    "observations": {"指标名称", "指标", "metric", "metric_name", "observation"},
    "medications": {"药品名称", "用药名称", "medication", "drug_name"},
    "medical_events": {"事件类型", "医疗事件", "event_type", "medical_event"},
    "services": {"服务名称", "服务结果", "service_name", "service_result"},
    "tasks": {"任务名称", "任务", "task_title", "task"},
    "members": {"姓名或显示名", "姓名", "display_name", "name"},
}

SHEET_TYPES = {
    "成员": "members", "members": "members",
    "健康数据": "observations", "observations": "observations", "health_data": "observations",
    "用药": "medications", "medications": "medications",
    "医疗事件": "medical_events", "medical_events": "medical_events",
    "服务结果": "services", "services": "services",
    "任务": "tasks", "tasks": "tasks",
    "体检结果": "reports", "reports": "reports",
}


class DataPackageError(ValueError):
    """A safe message that can be shown directly in the product UI."""


@dataclass(frozen=True)
class ImportIssue:
    message: str
    data_type: str = "健康数据"
    row_number: int | None = None


@dataclass(frozen=True)
class ImportPreviewRow:
    member: str
    metric: str
    value: str
    unit: str
    observed_at: str
    source: str
    matched_member_id: str | None = None


@dataclass
class PackageInspection:
    filename: str
    source: str
    package_hash: str
    schema_version: str
    package_name: str
    rows_by_type: dict[str, list[dict[str, Any]]]
    issues: list[ImportIssue] = field(default_factory=list)
    preview_rows: list[ImportPreviewRow] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    member_count: int = 0
    date_start: str | None = None
    date_end: str | None = None

    @property
    def valid(self) -> bool:
        return bool(self.rows_by_type) and self.schema_version == PACKAGE_SCHEMA_VERSION


@dataclass(frozen=True)
class PackageImportResult:
    status: str
    members: int
    created: int
    duplicates: int
    pending_review: int
    job_id: str
    previous_job_id: str | None = None


@dataclass(frozen=True)
class KnowledgePackageInspection:
    package_hash: str
    documents: tuple[dict[str, Any], ...]
    chunks: tuple[dict[str, Any], ...]
    source_count: int


def _suffix(name: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    return path.suffix.lower()


def _safe_archive_name(name: str) -> None:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise DataPackageError("压缩包包含不安全的文件路径。")
    if _suffix(name) not in {".csv", ".xlsx", ".json"}:
        raise DataPackageError("压缩包只能包含 CSV、XLSX 和 JSON 数据文件。")


def _json_depth(value: Any, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        return depth
    if isinstance(value, dict):
        return max((_json_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, list):
        return max((_json_depth(item, depth + 1) for item in value), default=depth)
    return depth


def _clean_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if len(text) > MAX_CELL_CHARS:
        raise DataPackageError("文件中存在过长的文本字段，请缩短后重试。")
    if text.startswith(("=", "+", "-", "@")) and not text.replace("-", "", 1).replace("+", "", 1).replace(".", "", 1).isdigit():
        raise DataPackageError("文件中包含可能执行公式的内容，已停止读取。")
    return text


def _records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if len(frame) > MAX_RECORDS:
        raise DataPackageError(f"单次最多导入 {MAX_RECORDS:,} 条记录。")
    return [{str(key).strip(): _clean_value(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def _canonical_fields(row: dict[str, Any]) -> dict[str, Any]:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    normalized: dict[str, Any] = {}
    for field_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lowered:
                normalized[field_name] = lowered[alias.lower()]
                break
    return normalized


def _infer_data_type(filename: str, rows: list[dict[str, Any]]) -> str:
    by_name = SHEET_TYPES.get(PurePosixPath(filename).stem.strip().lower())
    if by_name:
        return by_name
    columns = {str(key).strip().lower() for row in rows[:20] for key in row}
    for kind, hints in TYPE_FIELD_HINTS.items():
        if any(hint.lower() in columns for hint in hints):
            return kind
    return "observations"


class DataPackageAdapter:
    """Inspect external files and emit one canonical import representation."""

    def inspect(self, filename: str, content: bytes, *, source: str = "其他") -> PackageInspection:
        if len(content) > MAX_UPLOAD_BYTES:
            raise DataPackageError("文件超过 10 MB，请拆分后上传。")
        extension = _suffix(filename)
        if extension not in SUPPORTED_EXTENSIONS:
            raise DataPackageError("仅支持 ZIP、CSV、XLSX 和 JSON 数据包。")
        package_hash = hashlib.sha256(content).hexdigest()
        rows_by_type: dict[str, list[dict[str, Any]]] = {}
        manifest: dict[str, Any] = {}
        if extension == ".zip":
            rows_by_type, manifest = self._read_zip(content)
        else:
            rows_by_type = self._read_single(filename, content, data_type=None)
        schema_version = str(manifest.get("version") or PACKAGE_SCHEMA_VERSION)
        inspection = PackageInspection(
            filename=filename, source=source.strip() or "其他", package_hash=package_hash,
            schema_version=schema_version, package_name=str(manifest.get("package_name") or filename),
            rows_by_type=rows_by_type,
        )
        self.validate(inspection)
        return inspection

    def validate(self, inspection: PackageInspection) -> PackageInspection:
        if inspection.schema_version != PACKAGE_SCHEMA_VERSION:
            raise DataPackageError(f"该数据包版本暂不支持；当前支持 {PACKAGE_SCHEMA_VERSION}。")
        total = sum(len(rows) for rows in inspection.rows_by_type.values())
        if total == 0:
            raise DataPackageError("数据包中没有可导入的记录。")
        if total > MAX_RECORDS:
            raise DataPackageError(f"单次最多导入 {MAX_RECORDS:,} 条记录。")
        inspection.counts = {kind: len(rows) for kind, rows in inspection.rows_by_type.items()}
        members: set[str] = set()
        dates: list[datetime] = []
        for index, row in enumerate(inspection.rows_by_type.get("observations", []), 2):
            fields = _canonical_fields(row)
            missing = [name for name in ("external_member_id", "metric", "value", "observed_at") if not fields.get(name)]
            if missing:
                labels = {"external_member_id": "外部成员编号", "metric": "指标名称", "value": "数值", "observed_at": "采集时间"}
                inspection.issues.append(ImportIssue("缺少" + "、".join(labels[name] for name in missing), row_number=index))
                continue
            members.add(str(fields["external_member_id"]))
            try:
                observed = datetime.fromisoformat(str(fields["observed_at"]).replace("Z", "+00:00"))
                if observed.tzinfo is None:
                    raise ValueError
                dates.append(observed)
            except ValueError:
                inspection.issues.append(ImportIssue("采集时间格式无法识别或缺少时区", row_number=index))
            if canonical_code(str(fields["metric"])) is None:
                inspection.issues.append(ImportIssue(f"无法识别指标“{fields['metric']}”", row_number=index))
            else:
                try:
                    normalize_unit(canonical_code(str(fields["metric"])), fields["value"], str(fields.get("unit") or "") or None)  # type: ignore[arg-type]
                except ValueError:
                    inspection.issues.append(ImportIssue(f"数值或单位需要确认：{fields.get('value')} {fields.get('unit') or ''}".strip(), row_number=index))
            inspection.preview_rows.append(ImportPreviewRow(
                member=str(fields.get("external_member_id") or "待确认"), metric=str(fields.get("metric") or "待确认"),
                value=str(fields.get("value") or "未记录"), unit=str(fields.get("unit") or "待确认"),
                observed_at=str(fields.get("observed_at") or "待确认"), source=str(fields.get("source") or inspection.source),
            ))
        inspection.member_count = len(members)
        if dates:
            inspection.date_start = min(dates).date().isoformat()
            inspection.date_end = max(dates).date().isoformat()
        return inspection

    def preview(self, inspection: PackageInspection, *, limit: int = 20) -> list[ImportPreviewRow]:
        return inspection.preview_rows[: max(1, min(limit, 20))]

    def _read_single(self, filename: str, content: bytes, *, data_type: str | None) -> dict[str, list[dict[str, Any]]]:
        extension = _suffix(filename)
        if extension == ".csv":
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise DataPackageError("CSV 编码无法识别，请使用 UTF-8。") from exc
            try:
                frame = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=object)
            except (pd.errors.ParserError, csv.Error) as exc:
                raise DataPackageError("CSV 文件结构无法识别。") from exc
            rows = _records_from_frame(frame)
            return {data_type or _infer_data_type(filename, rows): rows}
        if extension == ".xlsx":
            try:
                sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=object)
            except Exception as exc:
                raise DataPackageError("Excel 文件无法读取；请确认文件未损坏且不含宏。") from exc
            result: dict[str, list[dict[str, Any]]] = {}
            for sheet_name, frame in sheets.items():
                kind = SHEET_TYPES.get(str(sheet_name).strip(), SHEET_TYPES.get(str(sheet_name).strip().lower()))
                if kind:
                    result.setdefault(kind, []).extend(_records_from_frame(frame))
            if not result:
                first = next(iter(sheets.values()), pd.DataFrame())
                result["observations"] = _records_from_frame(first)
            return result
        if extension == ".json":
            try:
                payload = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DataPackageError("JSON 文件无法读取。") from exc
            if _json_depth(payload) > MAX_JSON_DEPTH:
                raise DataPackageError("JSON 层级过深，已停止读取。")
            detected_type = data_type
            if isinstance(payload, dict):
                known_key = next((key for key in SHEET_TYPES if key in payload and isinstance(payload[key], list)), None)
                rows = payload.get("records", payload.get(known_key, [])) if known_key else payload.get("records", [])
                detected_type = detected_type or (SHEET_TYPES.get(known_key) if known_key else None)
            else:
                rows = payload
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise DataPackageError("JSON 需要包含记录列表。")
            cleaned = [{str(key): _clean_value(value) for key, value in row.items()} for row in rows]
            return {detected_type or _infer_data_type(filename, cleaned): cleaned}
        raise DataPackageError("不支持的数据文件。")

    def _read_zip(self, content: bytes) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        try:
            archive = ZipFile(io.BytesIO(content))
        except BadZipFile as exc:
            raise DataPackageError("ZIP 数据包已损坏或格式不正确。") from exc
        infos = [item for item in archive.infolist() if not item.is_dir()]
        if len(infos) > MAX_FILES:
            raise DataPackageError(f"压缩包最多包含 {MAX_FILES} 个数据文件。")
        total_size = sum(item.file_size for item in infos)
        if total_size > MAX_UNCOMPRESSED_BYTES:
            raise DataPackageError("压缩包解压后超过 20 MB。")
        if any(item.compress_size and item.file_size / item.compress_size > 100 for item in infos):
            raise DataPackageError("压缩包压缩比例异常，已停止读取。")
        for item in infos:
            path = PurePosixPath(item.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise DataPackageError("压缩包包含不安全的文件路径。")
            if PurePosixPath(item.filename).name == "manifest.json":
                continue
            _safe_archive_name(item.filename)
        manifest: dict[str, Any] = {}
        manifest_info = next((item for item in infos if PurePosixPath(item.filename).name == "manifest.json"), None)
        if manifest_info:
            try:
                manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DataPackageError("数据包说明文件无法读取。") from exc
            if not isinstance(manifest, dict) or _json_depth(manifest) > MAX_JSON_DEPTH:
                raise DataPackageError("数据包说明文件格式不正确。")
        declared = {
            str(row.get("path")): str(row.get("type"))
            for row in manifest.get("files", []) if isinstance(row, dict) and row.get("path")
        }
        result: dict[str, list[dict[str, Any]]] = {}
        for item in infos:
            if PurePosixPath(item.filename).name == "manifest.json":
                continue
            kind = declared.get(item.filename) or SHEET_TYPES.get(PurePosixPath(item.filename).stem.lower())
            loaded = self._read_single(item.filename, archive.read(item), data_type=kind)
            for data_type, rows in loaded.items():
                result.setdefault(data_type, []).extend(rows)
        if not result:
            raise DataPackageError("压缩包中没有可识别的数据文件。")
        return result, manifest


class KnowledgePackageAdapter:
    """Validate a source-complete knowledge ZIP before creating review items."""

    REQUIRED_FILES = {"documents.jsonl", "chunks.jsonl", "source_registry.json"}

    def inspect(self, content: bytes) -> KnowledgePackageInspection:
        if len(content) > MAX_UPLOAD_BYTES:
            raise DataPackageError("知识数据包超过 10 MB，请拆分后上传。")
        try:
            archive = ZipFile(io.BytesIO(content))
        except BadZipFile as exc:
            raise DataPackageError("知识数据包已损坏或格式不正确。") from exc
        infos = [item for item in archive.infolist() if not item.is_dir()]
        names = {PurePosixPath(item.filename).name for item in infos}
        if not self.REQUIRED_FILES <= names:
            raise DataPackageError("知识数据包缺少资料、知识片段或来源说明文件。")
        if sum(item.file_size for item in infos) > MAX_UNCOMPRESSED_BYTES:
            raise DataPackageError("知识数据包解压后超过 20 MB。")
        for item in infos:
            path = PurePosixPath(item.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise DataPackageError("知识数据包包含不安全的文件路径。")
        def json_lines(name: str) -> list[dict[str, Any]]:
            info = next(item for item in infos if PurePosixPath(item.filename).name == name)
            try:
                rows = [json.loads(line) for line in archive.read(info).decode("utf-8").splitlines() if line.strip()]
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DataPackageError(f"{name} 无法读取。") from exc
            if not all(isinstance(row, dict) for row in rows):
                raise DataPackageError(f"{name} 格式不正确。")
            return rows
        documents = json_lines("documents.jsonl")
        chunks = json_lines("chunks.jsonl")
        source_info = next(item for item in infos if PurePosixPath(item.filename).name == "source_registry.json")
        try:
            sources = json.loads(archive.read(source_info).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DataPackageError("来源说明文件无法读取。") from exc
        source_rows = sources.get("sources", sources) if isinstance(sources, dict) else sources
        if not isinstance(source_rows, list) or not source_rows:
            raise DataPackageError("知识数据包没有有效来源说明。")
        required = ("document_key", "title", "source", "organization", "version")
        for row in documents:
            if any(not str(row.get(field, "")).strip() for field in required):
                raise DataPackageError("知识资料必须包含名称、来源、机构和版本。")
        document_keys = {str(row["document_key"]) for row in documents}
        for row in chunks:
            if str(row.get("document_key", "")) not in document_keys or not str(row.get("content", "")).strip():
                raise DataPackageError("知识片段必须关联资料并包含内容。")
        return KnowledgePackageInspection(hashlib.sha256(content).hexdigest(), tuple(documents), tuple(chunks), len(source_rows))

    def import_for_review(self, session: Session, inspection: KnowledgePackageInspection) -> int:
        created = 0
        chunks_by_document: dict[str, list[dict[str, Any]]] = {}
        for chunk in inspection.chunks:
            chunks_by_document.setdefault(str(chunk["document_key"]), []).append(chunk)
        for row in inspection.documents:
            content_hash = hashlib.sha256((inspection.package_hash + str(row["document_key"])).encode("utf-8")).hexdigest()
            if session.scalar(select(KnowledgeDocument.id).where(KnowledgeDocument.content_hash == content_hash)):
                continue
            document = KnowledgeDocument(
                title=str(row["title"]), category=str(row.get("category") or "PATIENT_EDUCATION"),
                summary=str(row.get("summary") or "合作方知识数据包，等待人工审核。"),
                content_text="\n\n".join(str(item["content"]) for item in chunks_by_document.get(str(row["document_key"]), [])),
                source_type="合作方知识数据包", source_name=str(row["source"]),
                source_reference=str(row.get("source_url") or row["source"]), source_provider="PARTNER_PACKAGE",
                source_external_id=str(row["document_key"]), source_url=str(row.get("source_url") or "") or None,
                source_version=str(row["version"]), license_note=str(row.get("license_note") or "需在审核时确认"),
                attribution=str(row["organization"]), content_hash=content_hash,
                review_status="PENDING_REVIEW", is_active=True,
                metadata_json={"package_hash": inspection.package_hash, "pending_source_review": True},
            )
            session.add(document); session.flush()
            for index, chunk in enumerate(chunks_by_document.get(str(row["document_key"]), [])):
                content_text = str(chunk["content"])
                session.add(KnowledgeChunk(
                    knowledge_document_id=document.id, chunk_index=index,
                    heading=str(chunk.get("heading") or row["title"]), content=content_text,
                    source_location=str(chunk.get("section") or "未标章节"),
                    content_length=len(content_text), token_estimate=max(1, len(content_text) // 4),
                ))
            created += 1
        session.flush()
        return created


class HealthDataImportService:
    """Persist confirmed package observations through the existing ingestion path."""

    def unmatched_member_codes(self, session: Session, inspection: PackageInspection) -> list[str]:
        codes = {str(_canonical_fields(row).get("external_member_id") or "") for row in inspection.rows_by_type.get("observations", [])}
        unmatched: list[str] = []
        for code in sorted(item for item in codes if item):
            direct = session.scalar(select(Patient.id).where(Patient.external_id == code))
            identity = session.scalar(select(ExternalIdentity.id).where(ExternalIdentity.external_id == code, ExternalIdentity.status == "ACTIVE"))
            if direct is None and identity is None:
                unmatched.append(code)
        return unmatched

    def import_package(
        self, session: Session, inspection: PackageInspection, *, imported_by: str = "管理员",
        member_overrides: dict[str, str] | None = None,
    ) -> PackageImportResult:
        previous = session.scalar(select(IngestionJob).where(
            IngestionJob.source_system == "healthops_data_package",
            IngestionJob.external_sync_id == inspection.package_hash,
            IngestionJob.status.in_(("SUCCESS", "PARTIAL_SUCCESS")),
        ).order_by(IngestionJob.created_at.desc()))
        if previous:
            return PackageImportResult("DUPLICATE_PACKAGE", 0, 0, previous.records_duplicate, previous.error_count, str(previous.id), str(previous.id))
        root = IngestionJob(
            source_system="healthops_data_package", source_type="file", status="RUNNING",
            records_received=sum(inspection.counts.values()), created_by=imported_by,
            external_sync_id=inspection.package_hash, installation_id=inspection.source,
        )
        session.add(root); session.flush()
        created = duplicates = pending = 0
        member_ids: set[str] = set()
        try:
            for row in inspection.rows_by_type.get("observations", []):
                fields = _canonical_fields(row)
                if any(not fields.get(name) for name in ("external_member_id", "metric", "value", "observed_at")):
                    pending += 1
                    continue
                external_id = str(fields["external_member_id"])
                override = (member_overrides or {}).get(external_id)
                member = session.get(Patient, UUID(override)) if override and override != "CREATE_DRAFT" else None
                if override == "CREATE_DRAFT":
                    member = Patient(external_id=external_id, display_name=f"待完善成员 {external_id[-4:]}", timezone="Asia/Tokyo")
                    session.add(member); session.flush()
                member = member or session.scalar(select(Patient).where(Patient.external_id == external_id))
                if member is None:
                    identity = session.scalar(select(ExternalIdentity).where(ExternalIdentity.external_id == external_id, ExternalIdentity.status == "ACTIVE"))
                    member = session.get(Patient, identity.patient_id) if identity else None
                if member is None:
                    pending += 1
                    continue
                payload = {"records": [{
                    "id": hashlib.sha256((inspection.package_hash + json.dumps(row, sort_keys=True, ensure_ascii=False)).encode("utf-8")).hexdigest()[:32],
                    "metric": fields["metric"], "value": fields["value"], "unit": fields.get("unit") or None,
                    "observed_at": fields["observed_at"],
                }]}
                summary = ingest(session, "json", payload, member_id=member.id, created_by=imported_by)
                created += summary.created
                duplicates += summary.duplicates
                pending += summary.invalid + summary.unmatched
                member_ids.add(str(member.id))
            # Other record families are recognized and previewed, but remain
            # pending until their human confirmation workflows are selected.
            pending += sum(len(rows) for kind, rows in inspection.rows_by_type.items() if kind != "observations")
            root.records_valid = created + duplicates
            root.records_created = created
            root.records_duplicate = duplicates
            root.records_invalid = pending
            root.error_count = pending
            root.status = "SUCCESS" if pending == 0 else "PARTIAL_SUCCESS" if created or duplicates else "FAILED"
            root.completed_at = datetime.now(timezone.utc)
            session.flush()
        except Exception:
            session.rollback()
            raise
        return PackageImportResult(root.status, len(member_ids), created, duplicates, pending, str(root.id))


def build_healthops_template() -> bytes:
    """Create a business-facing workbook; no database or internal-code fields."""
    sheets = {
        "成员": pd.DataFrame([{"外部成员编号": "DEMO-001", "姓名或显示名": "演示成员", "说明": "使用双方约定的业务编号"}]),
        "健康数据": pd.DataFrame([{"外部成员编号": "DEMO-001", "指标名称": "收缩压", "数值": 120, "单位": "mmHg", "采集时间": "2026-09-01T08:00:00+09:00", "数据来源": "合作方"}]),
        "用药": pd.DataFrame([{"外部成员编号": "DEMO-001", "药品名称": "演示用药记录", "记录时间": "2026-09-01T08:00:00+09:00", "说明": "仅导入已有记录，不生成处方"}]),
        "医疗事件": pd.DataFrame([{"外部成员编号": "DEMO-001", "事件类型": "复查", "发生时间": "2026-09-01T08:00:00+09:00", "说明": "需人工确认"}]),
        "服务结果": pd.DataFrame([{"外部成员编号": "DEMO-001", "服务名称": "演示服务", "完成时间": "2026-09-01T08:00:00+09:00", "结果": "需人工确认"}]),
    }
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def build_synthetic_package(external_member_id: str = "portfolio-demo-executive-a") -> bytes:
    """Generate a small anonymous demo package without committing health data."""
    rows = [{
        "外部成员编号": external_member_id, "指标名称": "步数", "数值": "8200", "单位": "count",
        "采集时间": "2026-09-02T20:00:00+09:00", "数据来源": "匿名演示数据包",
    }]
    csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    manifest = {
        "package_name": "HealthOps 匿名演示数据包", "version": PACKAGE_SCHEMA_VERSION,
        "source": "synthetic", "generated_at": "2026-09-03T00:00:00+09:00",
        "files": [{"path": "observations.csv", "type": "observations"}],
    }
    output = io.BytesIO()
    from zipfile import ZIP_DEFLATED
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        archive.writestr("observations.csv", csv_bytes)
    return output.getvalue()
