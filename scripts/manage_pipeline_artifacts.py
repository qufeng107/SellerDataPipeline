from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.pipeline_artifact_repo import PipelineArtifactRepo
from seller_data_pipeline.services.pipeline_artifact_service import PipelineArtifactService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save, restore, list or prune Azure SQL pipeline artifacts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    save_parser = subparsers.add_parser(
        "save", help="Save local files/directories to artifact store."
    )
    save_parser.add_argument("--scope", required=True, help="Artifact scope key.")
    save_parser.add_argument("--root", default=".", help="Project root for relative paths.")
    save_parser.add_argument(
        "--path", action="append", required=True, help="File or directory to save."
    )
    save_parser.add_argument(
        "--modified-since",
        default=None,
        help="Only save files modified on/after this UTC ISO datetime.",
    )
    save_parser.add_argument("--expires-days", type=int, default=90, help="Retention days.")
    save_parser.add_argument("--max-file-mb", type=int, default=20, help="Per-file limit.")
    save_parser.add_argument("--execute", action="store_true", help="Actually write to Azure SQL.")

    restore_parser = subparsers.add_parser("restore", help="Restore latest artifacts for a scope.")
    restore_parser.add_argument("--scope", required=True, help="Artifact scope key.")
    restore_parser.add_argument("--output-root", default=".", help="Restore output root.")
    restore_parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Optional relative path prefix to restore. Repeatable.",
    )
    restore_parser.add_argument("--execute", action="store_true", help="Actually write files.")

    list_parser = subparsers.add_parser("list", help="List artifact metadata.")
    list_parser.add_argument("--scope", default=None, help="Optional artifact scope filter.")
    list_parser.add_argument("--type", default=None, help="Optional artifact type filter.")
    list_parser.add_argument("--limit", type=int, default=50, help="Max rows.")

    prune_parser = subparsers.add_parser("prune", help="Mark expired artifacts deleted.")
    prune_parser.add_argument("--execute", action="store_true", help="Actually mark rows deleted.")

    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)

    with get_connection(settings=settings, autocommit=True) as connection:
        service = PipelineArtifactService(repo=PipelineArtifactRepo(connection))
        if args.command == "save":
            modified_since = (
                datetime.fromisoformat(args.modified_since).astimezone(UTC)
                if args.modified_since
                else None
            )
            result = service.save_paths(
                artifact_scope=args.scope,
                paths=[Path(value) for value in args.path],
                root=args.root,
                modified_since=modified_since,
                expires_days=args.expires_days,
                max_file_mb=args.max_file_mb,
                dry_run=not args.execute,
            )
            print(
                f"Pipeline artifact save scope={result.artifact_scope} "
                f"mode={'execute' if not result.dry_run else 'dry_run'} "
                f"scanned={result.scanned_count} saved={result.saved_count} "
                f"skipped={result.skipped_count}"
            )
            for item in result.saved_artifacts:
                print(
                    f"- saved: id={item.artifact_id} type={item.artifact_type} "
                    f"path={item.relative_path} size={item.content_size_bytes} "
                    f"compressed={item.compressed_size_bytes} sha256={item.content_sha256[:12]}..."
                )
            if result.skipped_paths:
                print("skipped_paths:")
                for path in result.skipped_paths[:20]:
                    print(f"- {path}")
        elif args.command == "restore":
            result = service.restore_scope(
                artifact_scope=args.scope,
                output_root=args.output_root,
                path_prefixes=tuple(args.prefix),
                dry_run=not args.execute,
            )
            print(
                f"Pipeline artifact restore scope={result.artifact_scope} "
                f"mode={'execute' if not result.dry_run else 'dry_run'} "
                f"restored={result.restored_count}"
            )
            for item in result.restored_artifacts:
                print(
                    f"- restored: id={item.artifact_id} type={item.artifact_type} "
                    f"path={item.relative_path} output={item.output_path} "
                    f"size={item.content_size_bytes}"
                )
        elif args.command == "list":
            result = service.list_artifacts(
                artifact_scope=args.scope,
                artifact_type=args.type,
                limit=args.limit,
            )
            print(f"Pipeline artifacts count={len(result.artifacts)}")
            for item in result.artifacts:
                print(
                    f"- id={item.id} scope={item.artifact_scope} type={item.artifact_type} "
                    f"path={item.relative_path} size={item.content_size_bytes} "
                    f"created_at={item.created_at} expires_at={item.expires_at}"
                )
        elif args.command == "prune":
            result = service.prune_expired(dry_run=not args.execute)
            print(
                f"Pipeline artifact prune mode={'execute' if not result.dry_run else 'dry_run'} "
                f"deleted={result.deleted_count}"
            )


if __name__ == "__main__":
    run_cli_main(main)
