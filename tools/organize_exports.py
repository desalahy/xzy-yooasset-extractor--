from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


GROUPS = ("characters", "skills", "ui", "audio", "visual", "packets", "review")


CHARACTER_TABLES = {
    "TableAccessoryIndex",
    "TableCharacterIndex",
    "UiTableRole",
    "UiTableCharacterIndex",
    "UiTableCharacterParameter",
    "TableCharacterParameter",
    "TableCharacterTemplate",
    "TableCharacterExParameter",
    "TableCharacterVoice",
    "UiTableCore",
    "TableCoreIndex",
    "TableCoreType",
    "UiTableCoreType",
    "UiTableRoleArchives",
    "UiTableRoleAttributeMap",
    "UiTableRoleSceneCamOffset",
    "UiTableRoleType",
    "UiTableAccessory",
    "UiTableAccessorySet",
    "UiTablePainting",
    "UiTablePaintingFull",
    "UiTableCommonFreeCharacter",
    "UiTableMonthCardFreeCharacter",
    "UiTableLotteryPoolDisplayNew",
}

SKILL_TABLES = {
    "TableAmmoIndex",
    "TableBattleMessageIndex",
    "TableBattleModeIndex",
    "TableDamageIndex",
    "TableBuffIndex",
    "TableBulletIndex",
    "TableCharacterTalent",
    "TableCustomBattleMain",
    "TableDebuffIndex",
    "TableTalentIndex",
    "TableTimelineIndex",
    "UiTableGroupSkill",
    "UiTableGroupSkillBranch",
    "UiTableRoleSkillIcon",
    "UiTableCommonSkill",
    "UiTableRoleCommonRunes",
    "UiTableRoleRunesMain",
    "UiTableRoleRunesSlot",
    "UiTableRoleRunesGlobal",
    "UiTableRoleProficiency",
    "UiTableRoleProficiencyMain",
    "UiTableRoleProficiencyIcon",
    "UiTableTechniqueTrainingRole",
    "UiTableRoleTalent",
}

UI_TABLES = {
    "UiTableJumpAdBanner",
    "UiTableGlobal",
    "UiTableLoadingBackground",
    "UiTableBattleTutorial",
    "UiTableBattleMessageIndex",
    "UiTableMatchType",
    "UiTablePVEIndex",
    "UiTableStoryIndex",
    "UiTableDailyBonusLimit",
    "UiTableLeagueMatchLevel",
    "UiTableReplayTraceDays",
    "UiTableSettlementMain",
    "UiTableSettlementSeasonCoinDailyLimit",
    "UiTableCommunicationFunction",
    "UiTableGraphicGuide",
    "UiTableSystemTutorial",
    "UiTableBanpickCommunicationMain",
}

UI_PREFIXES = (
    "UiTableActivity",
    "UiTableGuide",
    "UiTableTutorial",
    "UiTableLobby",
    "UiTableMall",
    "UiTableRank",
    "UiTableSettlement",
)

DOMAIN_ORDER = {name: index for index, name in enumerate(GROUPS)}


ASSET_ALIAS_FILES = {
    "characters": {
        "prefabs": "character_prefabs.csv",
        "animation": "character_animation.csv",
    },
    "audio": {
        "bgm": "bgm.csv",
        "voice": "voice.csv",
        "sfx": "sfx.csv",
    },
    "skills": {
        "prefabs": "skill_prefabs.csv",
    },
    "visual": {
        "models": "models.csv",
        "textures": "textures.csv",
        "materials": "materials.csv",
        "effects": "effects.csv",
        "animation": "animation.csv",
        "prefabs": "prefabs.csv",
        "scenes": "scenes.csv",
        "spine": "spine.csv",
    },
    "ui": {
        "ui": "ui_assets.csv",
        "images": "ui_images.csv",
        "prefabs": "ui_prefabs.csv",
    },
}


TABLE_ALIAS_FILES = {
    "characters": {
        "base": "character_basic.csv",
        "stats": "character_stats.csv",
        "core": "character_core.csv",
        "profile": "character_profile.csv",
        "attributes": "character_attributes.csv",
        "camera": "character_camera.csv",
        "accessory": "character_accessory.csv",
        "art": "character_art.csv",
        "voice": "character_voice.csv",
    },
    "skills": {
        "battle": "battle_tables.csv",
        "buff": "skill_buffs.csv",
        "bullet": "skill_bullets.csv",
        "cooldown": "skill_cooldowns.csv",
        "damage": "skill_damage.csv",
        "skill_tree": "skill_groups.csv",
        "runes": "skill_runes.csv",
        "proficiency": "skill_proficiency.csv",
        "talent": "skill_talents.csv",
        "timeline": "skill_timelines.csv",
        "skill_ui": "skill_ui.csv",
        "technique": "skill_technique.csv",
        "skill": "skill_basic.csv",
    },
    "ui": {
        "activity": "activity_tables.csv",
        "banner": "banner_tables.csv",
        "tutorial": "tutorial_tables.csv",
        "system": "system_tables.csv",
        "mall": "mall_tables.csv",
        "rank": "rank_tables.csv",
        "settlement": "settlement_tables.csv",
        "match": "match_tables.csv",
        "lobby": "lobby_tables.csv",
    },
}


TEXT_ALIAS_FILES = {
    "characters": {
        "base": "character_texts.csv",
        "stats": "character_stats_texts.csv",
        "core": "character_core_texts.csv",
        "profile": "character_profile_texts.csv",
        "attributes": "character_attributes_texts.csv",
        "camera": "character_camera_texts.csv",
        "accessory": "character_accessory_texts.csv",
        "art": "character_art_texts.csv",
        "voice": "character_voice_texts.csv",
    },
    "skills": {
        "battle": "battle_texts.csv",
        "buff": "skill_buffs_texts.csv",
        "bullet": "skill_bullets_texts.csv",
        "cooldown": "skill_cooldowns_texts.csv",
        "damage": "skill_damage_texts.csv",
        "skill_tree": "skill_groups_texts.csv",
        "runes": "skill_runes_texts.csv",
        "proficiency": "skill_proficiency_texts.csv",
        "talent": "skill_talents_texts.csv",
        "timeline": "skill_timelines_texts.csv",
        "skill_ui": "skill_ui_texts.csv",
        "technique": "skill_technique_texts.csv",
        "skill": "skill_texts.csv",
    },
    "ui": {
        "activity": "activity_texts.csv",
        "banner": "banner_texts.csv",
        "tutorial": "tutorial_texts.csv",
        "system": "system_texts.csv",
        "mall": "mall_texts.csv",
        "rank": "rank_texts.csv",
        "settlement": "settlement_texts.csv",
        "match": "match_texts.csv",
        "lobby": "lobby_texts.csv",
    },
}


ASSET_FIELDS = [
    "business_domain",
    "business_subdomain",
    "business_reason",
    "availability",
    "layout",
    "package",
    "bundle_hash",
    "bundle_mode",
    "source",
    "type",
    "path_id",
    "asset_name",
    "category",
    "output",
    "status",
    "manifest_reference",
    "manifest_match",
]

BUNDLE_FIELDS = [
    "layout",
    "package",
    "bundle_hash",
    "mode",
    "source",
    "length",
    "raw_head",
    "decoded_head",
    "manifest_reference",
    "manifest_match",
]

TABLE_INDEX_FIELDS = [
    "business_domain",
    "business_subdomain",
    "confidence",
    "business_reason",
    "rel_path",
    "status",
    "table_name",
    "match_status",
    "packet_asset_name",
    "packet_asset_path",
    "row_count",
    "column_count",
    "types",
    "consumed",
    "candidate_tables",
    "field_names",
    "error",
]

TABLE_ROW_FIELDS = [
    "business_domain",
    "business_subdomain",
    "confidence",
    "business_reason",
    "table_name",
    "match_status",
    "packet_asset_name",
    "packet_asset_path",
    "rel_path",
    "row_index",
    "row_id",
    "field_path",
    "value_kind",
    "value",
]

TEXT_FIELDS = [
    "business_domain",
    "business_subdomain",
    "confidence",
    "business_reason",
    "table_name",
    "match_status",
    "packet_asset_name",
    "packet_asset_path",
    "rel_path",
    "row_index",
    "row_id",
    "field_name",
    "text_kind",
    "text",
]


class CsvSink:
    def __init__(self, path: Path, fieldnames: list[str]) -> None:
        self.path = path
        self.fieldnames = fieldnames
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("w", encoding="utf-8-sig", newline="")
        self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames, extrasaction="ignore")
        self.writer.writeheader()
        self.count = 0

    def write(self, row: dict[str, Any]) -> None:
        self.writer.writerow(row)
        self.count += 1

    def close(self) -> None:
        self.file.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize XZY extractor outputs into business indexes.")
    parser.add_argument("--input", required=True, help="Root directory containing assets.csv and bin_probe/.")
    parser.add_argument("--out", required=True, help="Output directory for organized business indexes.")
    parser.add_argument("--assets-csv", help="Optional explicit assets.csv path.")
    parser.add_argument("--bundles-csv", help="Optional explicit bundles.csv path.")
    parser.add_argument("--table-probe", help="Optional table probe directory with table_bins.csv and tables_json/.")
    parser.add_argument("--table-texts", help="Optional table_texts.csv file or directory.")
    parser.add_argument("--binary-probe", help="Optional binary probe directory with binary_bins.csv.")
    parser.add_argument("--write-json", action="store_true", help="Also write JSON mirrors for key indexes.")
    return parser.parse_args(argv)


def normalize_rel_path(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def lower(value: Any) -> str:
    return str(value or "").casefold()


def split_multi(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[|,]", value) if part.strip()]


def load_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_csv_rows_stream(path: Path | None) -> Iterable[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        yield from csv.DictReader(file)


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def availability_from_status(status: str) -> str:
    status_lower = lower(status)
    if status_lower.startswith("exported_") or status_lower.startswith("copied_"):
        return "materialized"
    if status_lower == "listed_only":
        return "listed_only"
    if not status_lower:
        return "unknown"
    return status_lower


def asset_group_hint(row: dict[str, str]) -> tuple[str, str]:
    category = lower(row.get("category"))
    package = lower(row.get("package"))
    asset_name = lower(row.get("asset_name"))
    source = lower(row.get("source"))
    type_name = lower(row.get("type"))

    if category == "bgm":
        return "audio", "bgm"
    if category == "audio":
        if "voice" in package or "voice" in asset_name or "voice" in source:
            return "audio", "voice"
        return "audio", "sfx"
    if category == "ui":
        return "ui", "ui"
    if category == "textures":
        if "icon" in package or "icon" in asset_name or "ui" in source:
            return "ui", "images"
        return "visual", "textures"
    if category == "models":
        return "visual", "models"
    if category == "materials":
        return "visual", "materials"
    if category == "effects":
        return "visual", "effects"
    if category == "animation":
        if "character" in package or "spine" in package or "timeline" in package or "performance" in package:
            return "characters", "animation"
        return "visual", "animation"
    if category == "prefabs":
        if "voice" in package:
            return "audio", "voice"
        if "character" in package or "character" in asset_name:
            return "characters", "prefabs"
        if "skill" in package or "rune" in package or "talent" in package:
            return "skills", "prefabs"
        if "icon" in package or "ui" in package or "main" in package:
            return "ui", "prefabs"
        if "spine" in package:
            return "visual", "spine"
        if "effect" in package:
            return "visual", "effects"
        if "battle" in package or "scene" in package:
            return "visual", "scenes"
        return "visual", "prefabs"
    if category == "text":
        if "packet" in source or "packet" in package or "table" in source:
            return "packets", "text"
        return "ui", "text"
    if category == "raw":
        return "packets", "raw"
    if category == "other":
        if "packet" in source or "packet" in package:
            return "packets", "other"
        return "review", "other"

    if "packet" in source or "packet" in package:
        return "packets", "other"
    if "voice" in package:
        return "audio", "voice"
    if "icon" in package or "ui" in package:
        return "ui", "misc"
    if "character" in package:
        return "characters", "misc"
    if "effect" in package:
        return "visual", "effects"
    if type_name == "audioclip":
        return "audio", "sfx"
    if type_name in {"texture2d", "sprite"}:
        return "visual", "textures"
    return "review", "unclassified"


def classify_asset(row: dict[str, str]) -> tuple[str, str, str, str]:
    domain, subdomain = asset_group_hint(row)
    status = row.get("status", "")
    reason = f"category={row.get('category', '')}; package={row.get('package', '')}; type={row.get('type', '')}; status={status}"
    return domain, subdomain, availability_from_status(status), reason


def table_group_hint(table_name: str) -> tuple[str, str]:
    name = table_name or ""
    if not name:
        return "review", "unassigned"
    if name.startswith("UiTableActivity"):
        return "ui", "activity"
    if name in UI_TABLES or any(name.startswith(prefix) for prefix in UI_PREFIXES):
        if "banner" in lower(name):
            return "ui", "banner"
        if "tutorial" in lower(name) or "guide" in lower(name):
            return "ui", "tutorial"
        if "mall" in lower(name):
            return "ui", "mall"
        if "lobby" in lower(name):
            return "ui", "lobby"
        if "rank" in lower(name):
            return "ui", "rank"
        if "settlement" in lower(name):
            return "ui", "settlement"
        if "match" in lower(name):
            return "ui", "match"
        return "ui", "system"
    if name in SKILL_TABLES:
        if "ammo" in lower(name):
            return "skills", "cooldown"
        if "battlemessage" in lower(name) or "battlemode" in lower(name) or "custombattle" in lower(name):
            return "skills", "battle"
        if "buff" in lower(name):
            return "skills", "buff"
        if "bullet" in lower(name):
            return "skills", "bullet"
        if "damage" in lower(name):
            return "skills", "damage"
        if "groupskill" in lower(name):
            return "skills", "skill_tree"
        if "skillicon" in lower(name):
            return "skills", "skill_ui"
        if "runes" in lower(name):
            return "skills", "runes"
        if "proficiency" in lower(name):
            return "skills", "proficiency"
        if "talent" in lower(name):
            return "skills", "talent"
        if "timeline" in lower(name):
            return "skills", "timeline"
        if "technique" in lower(name):
            return "skills", "technique"
        return "skills", "skill"
    if name in CHARACTER_TABLES:
        if "voice" in lower(name):
            return "characters", "voice"
        if "parameter" in lower(name):
            return "characters", "stats"
        if "scenecamoffset" in lower(name):
            return "characters", "camera"
        if "archives" in lower(name):
            return "characters", "profile"
        if "attribute" in lower(name):
            return "characters", "attributes"
        if "painting" in lower(name):
            return "characters", "art"
        if "accessory" in lower(name):
            return "characters", "accessory"
        if "core" in lower(name):
            return "characters", "core"
        return "characters", "base"
    return "review", "unassigned"


def table_confidence(match_status: str, table_name: str) -> str:
    if not table_name:
        return "low"
    status = lower(match_status)
    if status in {"unique_signature", "package_preferred"}:
        return "high"
    if status == "package_ambiguous":
        return "medium"
    if status == "ambiguous_signature":
        return "low"
    if status == "no_match":
        return "low"
    return "medium"


def infer_table_domain(row: dict[str, str]) -> tuple[str, str, str]:
    table_name = row.get("table_name", "") or ""
    match_status = row.get("match_status", "") or ""
    domain, subdomain = table_group_hint(table_name)
    confidence = table_confidence(match_status, table_name)
    candidate_tables = split_multi(row.get("candidate_tables", ""))

    if domain == "review" and candidate_tables:
        candidate_domains = {table_group_hint(candidate)[0] for candidate in candidate_tables}
        candidate_domains.discard("review")
        if len(candidate_domains) == 1:
            domain = candidate_domains.pop()
            subdomain = table_group_hint(candidate_tables[0])[1]
            confidence = "low"
    if not table_name and candidate_tables:
        confidence = "low"
    reason = f"table={table_name or 'unknown'}; match_status={match_status}"
    if candidate_tables:
        reason += f"; candidates={len(candidate_tables)}"
    return domain, subdomain, confidence, reason


def pick_row_id(row: dict[str, Any]) -> str:
    for key in ("Id", "ID", "id", "RoleId", "CharacterId", "CoreID", "CoreId", "EventId", "MissionId", "ItemId", "SkillId", "Key", "Index"):
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return ""


def scalar_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return type(value).__name__.lower()


def scalar_text(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def flatten_scalars(value: Any, prefix: str = "") -> Iterable[tuple[str, str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten_scalars(child, child_prefix)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            yield from flatten_scalars(child, child_prefix)
        return
    if prefix:
        yield prefix, scalar_kind(value), scalar_text(value)


def resolve_table_probe(input_root: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.exists():
            return path
        raise SystemExit(f"table probe path does not exist: {path}")
    candidates = [
        input_root / "bin_probe" / "table_bin_probe_v6_named",
        input_root / "bin_probe" / "table_bin_probe_named",
        input_root / "bin_probe" / "table_bin_probe",
        input_root / "table_bin_probe_v6_named",
        input_root / "table_bin_probe_named",
    ]
    return first_existing(candidates)


def resolve_table_texts_csv(input_root: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_dir():
            candidate = path / "table_texts.csv"
            if candidate.exists():
                return candidate
            raise SystemExit(f"table_texts.csv not found in: {path}")
        if path.exists():
            return path
        raise SystemExit(f"table texts path does not exist: {path}")
    candidates = [
        input_root / "table_texts_all" / "table_texts.csv",
        input_root / "table_texts_activity" / "table_texts.csv",
        input_root / "table_texts.csv",
    ]
    return first_existing(candidates)


def resolve_binary_probe_csv(input_root: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_dir():
            candidate = path / "binary_bins.csv"
            if candidate.exists():
                return candidate
            raise SystemExit(f"binary_bins.csv not found in: {path}")
        if path.exists():
            return path
        raise SystemExit(f"binary probe path does not exist: {path}")
    candidates = [
        input_root / "bin_probe" / "binary_probe_named" / "binary_bins.csv",
        input_root / "bin_probe" / "binary_probe_v6_named" / "binary_bins.csv",
        input_root / "binary_probe_named" / "binary_bins.csv",
    ]
    return first_existing(candidates)


def load_table_meta_by_name(table_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for row in table_rows:
        table_name = row.get("table_name", "")
        if table_name and table_name not in mapping:
            mapping[table_name] = row
    return mapping


def ensure_sink(sinks: dict[str, CsvSink], rel_path: str, fieldnames: list[str], out_root: Path) -> CsvSink:
    sink = sinks.get(rel_path)
    if sink is None:
        sink = CsvSink(out_root / rel_path, fieldnames)
        sinks[rel_path] = sink
    return sink


def write_json_if_requested(path: Path, payload: Any, enabled: bool) -> None:
    if not enabled:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_output_readme(out_root: Path, summary: dict[str, Any]) -> None:
    assets_by_domain = summary["assets"]["by_domain"]
    tables_by_domain = summary["tables"]["by_domain"]
    readme_lines = [
        "# XZY Organized Browser",
        "",
        "This directory is a browsing layer over the raw extractor output.",
        "It keeps the original evidence intact and adds human-oriented indexes.",
        "",
        "## First Open",
        "- `_index/summary.json`",
        "- `_index/assets_index.csv`",
        "- `characters/tables.csv`",
        "- `skills/tables.csv`",
        "- `ui/tables.csv`",
        "- `ui/texts.csv`",
        "- `review/tables.csv`",
        "- `review/no_match_tables.csv`",
        "- `review/ambiguous_tables.csv`",
        "- `packets/tables.csv`",
        "- `packets/texts.csv`",
        "",
        "## Bucket Map",
        "- `characters/`: base stats, role, voice, profile, accessories, and art",
        "- `skills/`: cooldown, damage, skill tree, runes, proficiency, and technique tables",
        "- `ui/`: activity, banner, tutorial, system, lobby, rank, settlement, and match tables",
        "- `audio/`: bgm, voice, and sfx asset lists",
        "- `visual/`: models, textures, materials, effects, animation, prefabs, scenes, and spine assets",
        "- `packets/`: parsed packet tables and searchable table text rows",
        "- `review/`: ambiguous rows, no-match tables, and non-table binary leftovers",
        "",
        "## Summary",
        f"- Assets rows: {summary['assets']['rows']}",
        f"- Tables rows: {summary['tables']['rows']}",
        f"- Selected table rows: {summary['tables']['selected_rows']}",
        f"- Selected text rows: {summary['tables']['selected_text_rows']}",
        f"- Binary probe rows: {summary['binary_probe']['rows']}",
        "",
        "### Assets By Domain",
    ]
    if assets_by_domain:
        for domain, count in assets_by_domain.items():
            readme_lines.append(f"- {domain}: {count}")
    else:
        readme_lines.append("- none")
    readme_lines.extend(
        [
            "",
            "### Tables By Domain",
        ]
    )
    if tables_by_domain:
        for domain, count in tables_by_domain.items():
            readme_lines.append(f"- {domain}: {count}")
    else:
        readme_lines.append("- none")
    if summary["binary_probe"]["present"]:
        readme_lines.extend(
            [
                "",
                "## Binary Probe",
                "- `review/non_table_bins.csv`",
            ]
        )
    readme_lines.append("")
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")


def alias_path(alias_files: dict[str, dict[str, str]], domain: str, subdomain: str) -> str | None:
    filename = alias_files.get(domain, {}).get(subdomain)
    if filename is None:
        return None
    return f"{domain}/{filename}"


def write_alias_copy(
    sinks: dict[str, CsvSink],
    out_root: Path,
    alias_files: dict[str, dict[str, str]],
    domain: str,
    subdomain: str,
    fieldnames: list[str],
    row: dict[str, Any],
) -> None:
    rel_path = alias_path(alias_files, domain, subdomain)
    if rel_path is None:
        return
    ensure_sink(sinks, rel_path, fieldnames, out_root).write(row)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_root = Path(args.input).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    if not input_root.exists():
        raise SystemExit(f"input root does not exist: {input_root}")

    assets_csv = Path(args.assets_csv).expanduser().resolve() if args.assets_csv else input_root / "assets.csv"
    if not assets_csv.exists():
        raise SystemExit(f"assets.csv not found: {assets_csv}")

    bundles_csv = Path(args.bundles_csv).expanduser().resolve() if args.bundles_csv else input_root / "bundles.csv"
    table_probe = resolve_table_probe(input_root, args.table_probe)
    table_texts_csv = resolve_table_texts_csv(input_root, args.table_texts)
    binary_probe_csv = resolve_binary_probe_csv(input_root, args.binary_probe)

    table_bins_rows = load_csv_rows(table_probe / "table_bins.csv") if table_probe else []
    table_meta_by_name = load_table_meta_by_name(table_bins_rows)

    bundle_rows = load_csv_rows(bundles_csv)

    # Sinks that are always present.
    sinks: dict[str, CsvSink] = {}

    def add_sink(rel_path: str, fieldnames: list[str]) -> CsvSink:
        sink = CsvSink(out_root / rel_path, fieldnames)
        sinks[rel_path] = sink
        return sink

    all_assets_sink = add_sink("_index/assets_index.csv", ASSET_FIELDS)
    bundles_sink = add_sink("_index/bundles_index.csv", BUNDLE_FIELDS)
    packets_tables_sink = add_sink("packets/tables.csv", TABLE_INDEX_FIELDS)
    review_tables_sink = add_sink("review/tables.csv", TABLE_INDEX_FIELDS)
    review_ambiguous_sink = add_sink("review/ambiguous_tables.csv", TABLE_INDEX_FIELDS)
    review_no_match_sink = add_sink("review/no_match_tables.csv", TABLE_INDEX_FIELDS)
    packets_table_rows_sink = add_sink("packets/table_rows.csv", TABLE_ROW_FIELDS)
    packets_texts_sink = add_sink("packets/texts.csv", TEXT_FIELDS)
    review_table_rows_sink = add_sink("review/table_rows.csv", TABLE_ROW_FIELDS)
    review_texts_sink = add_sink("review/texts.csv", TEXT_FIELDS)

    domain_asset_sinks = {group: add_sink(f"{group}/assets.csv", ASSET_FIELDS) for group in GROUPS}
    domain_table_sinks = {group: add_sink(f"{group}/tables.csv", TABLE_INDEX_FIELDS) for group in ("characters", "skills", "ui")}
    domain_row_sinks = {group: add_sink(f"{group}/table_rows.csv", TABLE_ROW_FIELDS) for group in ("characters", "skills", "ui")}
    domain_text_sinks = {group: add_sink(f"{group}/texts.csv", TEXT_FIELDS) for group in ("characters", "skills", "ui")}

    domain_table_counts: Counter[str] = Counter()
    domain_asset_counts: Counter[str] = Counter()
    domain_text_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    match_status_counts: Counter[str] = Counter()
    asset_status_counts: Counter[str] = Counter()
    bundle_mode_counts: Counter[str] = Counter()
    selected_table_rows = 0
    selected_text_rows = 0

    # Bundles.
    for row in bundle_rows:
        bundles_sink.write({field: row.get(field, "") for field in BUNDLE_FIELDS})
        bundle_mode_counts[row.get("mode", "")] += 1

    # Assets, streamed to avoid holding the full file in memory.
    for row in load_csv_rows_stream(assets_csv):
        domain, subdomain, availability, reason = classify_asset(row)
        asset_status_counts[row.get("status", "")] += 1
        domain_asset_counts[domain] += 1
        output_row = {
            "business_domain": domain,
            "business_subdomain": subdomain,
            "business_reason": reason,
            "availability": availability,
            **{field: row.get(field, "") for field in ASSET_FIELDS if field not in {"business_domain", "business_subdomain", "business_reason", "availability"}},
        }
        all_assets_sink.write(output_row)
        domain_asset_sinks[domain].write(output_row)
        write_alias_copy(sinks, out_root, ASSET_ALIAS_FILES, domain, subdomain, ASSET_FIELDS, output_row)

    # Table metadata.
    parsed_table_meta: list[dict[str, str]] = []
    review_meta_rows: list[dict[str, str]] = []
    for row in table_bins_rows:
        domain, subdomain, confidence, reason = infer_table_domain(row)
        match_status = row.get("match_status", "")
        status = row.get("status", "")
        confidence_counts[confidence] += 1
        match_status_counts[match_status] += 1
        domain_table_counts[domain] += 1
        table_index_row = {
            "business_domain": domain,
            "business_subdomain": subdomain,
            "confidence": confidence,
            "business_reason": reason,
            "rel_path": normalize_rel_path(row.get("rel_path", "")),
            "status": status,
            "table_name": row.get("table_name", ""),
            "match_status": match_status,
            "packet_asset_name": row.get("packet_asset_name", ""),
            "packet_asset_path": row.get("packet_asset_path", ""),
            "row_count": row.get("row_count", ""),
            "column_count": row.get("column_count", ""),
            "types": row.get("types", ""),
            "consumed": row.get("consumed", ""),
            "candidate_tables": row.get("candidate_tables", ""),
            "field_names": row.get("field_names", ""),
            "error": row.get("error", ""),
        }
        packets_tables_sink.write(table_index_row)
        if domain in domain_table_sinks:
            domain_table_sinks[domain].write(table_index_row)
        write_alias_copy(sinks, out_root, TABLE_ALIAS_FILES, domain, subdomain, TABLE_INDEX_FIELDS, table_index_row)
        if confidence != "high" or domain == "review":
            review_tables_sink.write(table_index_row)
            review_meta_rows.append(table_index_row)
            if match_status == "no_match":
                review_no_match_sink.write(table_index_row)
            elif match_status in {"ambiguous_signature", "package_ambiguous"}:
                review_ambiguous_sink.write(table_index_row)
        parsed_table_meta.append(table_index_row)

    # Flatten selected tables into the packet/character/skill/ui row indexes.
    tables_json_root = table_probe / "tables_json" if table_probe else None
    if tables_json_root is not None and tables_json_root.exists():
        for meta in parsed_table_meta:
            domain = meta["business_domain"]
            if domain not in {"characters", "skills", "ui"}:
                continue
            rel_path = meta["rel_path"]
            json_path = tables_json_root / f"{rel_path}.json"
            if not json_path.exists():
                continue
            try:
                table_rows = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                review_reason = f"{meta['business_reason']}; json_error={exc}"
                review_tables_sink.write({**meta, "business_reason": review_reason})
                continue
            if not isinstance(table_rows, list):
                continue
            for row_index, table_row in enumerate(table_rows):
                if not isinstance(table_row, dict):
                    continue
                row_id = pick_row_id(table_row)
                for field_path, value_kind, value in flatten_scalars(table_row):
                    row_record = {
                        "business_domain": domain,
                        "business_subdomain": meta["business_subdomain"],
                        "confidence": meta["confidence"],
                        "business_reason": meta["business_reason"],
                        "table_name": meta["table_name"],
                        "match_status": meta["match_status"],
                        "packet_asset_name": meta["packet_asset_name"],
                        "packet_asset_path": meta["packet_asset_path"],
                        "rel_path": meta["rel_path"],
                        "row_index": row_index,
                        "row_id": row_id,
                        "field_path": field_path,
                        "value_kind": value_kind,
                        "value": value,
                    }
                    packets_table_rows_sink.write(row_record)
                    domain_row_sinks[domain].write(row_record)
                    selected_table_rows += 1
                    if meta["confidence"] != "high":
                        review_table_rows_sink.write(row_record)

    # Filter text rows for the selected groups.
    if table_texts_csv is not None and table_texts_csv.exists():
        for row in load_csv_rows_stream(table_texts_csv):
            table_name = row.get("table_name", "")
            domain, subdomain = table_group_hint(table_name)
            if domain not in {"characters", "skills", "ui"}:
                continue
            meta = table_meta_by_name.get(table_name, {})
            confidence = table_confidence(row.get("match_status", meta.get("match_status", "")), table_name)
            reason = f"table={table_name or 'unknown'}; field={row.get('field_name', '')}"
            text_row = {
                "business_domain": domain,
                "business_subdomain": subdomain,
                "confidence": confidence,
                "business_reason": reason,
                "table_name": table_name,
                "match_status": row.get("match_status", meta.get("match_status", "")),
                "packet_asset_name": row.get("packet_asset_name", meta.get("packet_asset_name", "")),
                "packet_asset_path": row.get("packet_asset_path", meta.get("packet_asset_path", "")),
                "rel_path": normalize_rel_path(row.get("rel_path", meta.get("rel_path", ""))),
                "row_index": row.get("row_index", ""),
                "row_id": row.get("row_id", ""),
                "field_name": row.get("field_name", ""),
                "text_kind": row.get("text_kind", ""),
                "text": row.get("text", ""),
            }
            packets_texts_sink.write(text_row)
            domain_text_sinks[domain].write(text_row)
            write_alias_copy(sinks, out_root, TEXT_ALIAS_FILES, domain, subdomain, TEXT_FIELDS, text_row)
            selected_text_rows += 1
            domain_text_counts[domain] += 1
            if confidence != "high":
                review_texts_sink.write(text_row)

    # Optional binary probe snapshot.
    binary_rows: list[dict[str, str]] = []
    if binary_probe_csv is not None and binary_probe_csv.exists():
        binary_rows = load_csv_rows(binary_probe_csv)
        binary_sink = add_sink("_index/binary_index.csv", [field for field in binary_rows[0].keys()] if binary_rows else ["rel_path"])
        review_binary_sink = add_sink("review/non_table_bins.csv", [field for field in binary_rows[0].keys()] if binary_rows else ["rel_path"])
        for row in binary_rows:
            binary_sink.write(row)
            if lower(row.get("status")) != "table":
                review_binary_sink.write(row)

    summary = {
        "input_root": str(input_root),
        "out_root": str(out_root),
        "assets": {
            "rows": sum(domain_asset_counts.values()),
            "by_domain": dict(sorted(domain_asset_counts.items(), key=lambda item: DOMAIN_ORDER.get(item[0], 999))),
            "by_status": dict(asset_status_counts.most_common()),
        },
        "bundles": {
            "rows": len(bundle_rows),
            "by_mode": dict(bundle_mode_counts.most_common()),
        },
        "tables": {
            "rows": len(table_bins_rows),
            "by_domain": dict(sorted(domain_table_counts.items(), key=lambda item: DOMAIN_ORDER.get(item[0], 999))),
            "by_match_status": dict(match_status_counts.most_common()),
            "by_confidence": dict(confidence_counts.most_common()),
            "selected_rows": selected_table_rows,
            "selected_text_rows": selected_text_rows,
        },
        "binary_probe": {
            "rows": len(binary_rows),
            "present": bool(binary_rows),
        },
    }

    write_json_if_requested(out_root / "_index" / "summary.json", summary, True)
    write_output_readme(out_root, summary)

    if args.write_json:
        write_json_if_requested(out_root / "_index" / "bundles.json", bundle_rows, True)
        write_json_if_requested(out_root / "packets" / "tables.json", table_bins_rows, True)
        write_json_if_requested(out_root / "review" / "tables.json", review_meta_rows, True)
        if binary_rows:
            write_json_if_requested(out_root / "review" / "non_table_bins.json", binary_rows, True)

    for sink in sinks.values():
        sink.close()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
