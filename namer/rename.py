"""Core rename logic: prefix, case, and numbering transforms."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CaseMode(str, Enum):
    NONE = "none"
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"


class NumberPosition(str, Enum):
    """Where the number sits relative to the stem (always before the extension)."""

    BEFORE_STEM = "before_stem"  # 001_name.ext
    AFTER_STEM = "after_stem"  # name_001.ext


@dataclass
class RenameOptions:
    remove_common_prefix: bool = False
    prefix_to_remove: str = ""  # empty → auto-detect longest common prefix of stems
    add_prefix: str = ""
    case_mode: CaseMode = CaseMode.NONE
    number: bool = False
    number_start: int = 1
    number_digits: int = 3
    number_separator: str = "_"
    number_position: NumberPosition = NumberPosition.AFTER_STEM
    include_extensions: bool = True  # keep original extensions


@dataclass
class RenamePlan:
    """Mapping of source paths to proposed destination paths."""

    items: list[tuple[Path, Path]] = field(default_factory=list)
    common_prefix_detected: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> list[tuple[Path, Path]]:
        return [(src, dst) for src, dst in self.items if src.name != dst.name]


def longest_common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def list_files(folder: Path, *, recursive: bool = False) -> list[Path]:
    if not folder.is_dir():
        return []
    if recursive:
        return sorted(p for p in folder.rglob("*") if p.is_file())
    return sorted(p for p in folder.iterdir() if p.is_file())


def _apply_case(stem: str, mode: CaseMode) -> str:
    if mode is CaseMode.LOWER:
        return stem.lower()
    if mode is CaseMode.UPPER:
        return stem.upper()
    if mode is CaseMode.TITLE:
        return stem.title()
    return stem


def transform_stem(
    stem: str,
    *,
    index: int,
    options: RenameOptions,
    common_prefix: str,
) -> str:
    result = stem

    if options.remove_common_prefix and common_prefix and result.startswith(common_prefix):
        result = result[len(common_prefix) :]

    result = _apply_case(result, options.case_mode)

    if options.add_prefix:
        result = options.add_prefix + result

    if options.number:
        num = str(options.number_start + index).zfill(options.number_digits)
        sep = options.number_separator
        if options.number_position is NumberPosition.BEFORE_STEM:
            result = f"{num}{sep}{result}" if result else num
        else:
            result = f"{result}{sep}{num}" if result else num

    return result or "_"


def build_plan(
    folder: Path,
    options: RenameOptions,
    *,
    recursive: bool = False,
) -> RenamePlan:
    files = list_files(folder, recursive=recursive)
    plan = RenamePlan()

    if not files:
        plan.errors.append("フォルダ内にファイルがありません。")
        return plan

    stems = [f.stem for f in files]
    if options.remove_common_prefix:
        if options.prefix_to_remove:
            common = options.prefix_to_remove
        else:
            common = longest_common_prefix(stems)
            # Avoid stripping everything when all stems are identical
            if common and all(s == common for s in stems):
                common = ""
        plan.common_prefix_detected = common
    else:
        common = ""

    used_names: dict[str, Path] = {}
    for i, src in enumerate(files):
        new_stem = transform_stem(
            src.stem,
            index=i,
            options=options,
            common_prefix=common,
        )
        suffix = src.suffix if options.include_extensions else ""
        dst = src.with_name(new_stem + suffix)

        key = str(dst.resolve()).lower()
        if key in used_names:
            plan.errors.append(
                f"名前の衝突: '{src.name}' と '{used_names[key].name}' → '{dst.name}'"
            )
        else:
            used_names[key] = src

        if dst.exists() and dst.resolve() != src.resolve():
            plan.errors.append(f"既に存在します: '{dst.name}' ← '{src.name}'")

        plan.items.append((src, dst))

    return plan


def apply_plan(plan: RenamePlan) -> list[str]:
    """Apply renames safely (two-phase to avoid overwrite collisions). Returns log lines."""
    if plan.errors:
        raise ValueError("エラーがあるためリネームを実行できません。")

    changed = plan.changed
    if not changed:
        return ["変更はありませんでした。"]

    logs: list[str] = []
    # Phase 1: rename to unique temporary names
    temps: list[tuple[Path, Path, Path]] = []  # src, tmp, dst
    for i, (src, dst) in enumerate(changed):
        tmp = src.with_name(f".__namer_tmp_{i}__{src.name}")
        src.rename(tmp)
        temps.append((src, tmp, dst))

    # Phase 2: rename temps to final names
    for src, tmp, dst in temps:
        tmp.rename(dst)
        logs.append(f"{src.name}  →  {dst.name}")

    return logs
