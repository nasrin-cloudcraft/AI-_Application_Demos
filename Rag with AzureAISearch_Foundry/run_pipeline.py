"""
run_pipeline.py — Run pipeline for BOTH indexes.

CHANGE: loops through config.INDEXES, calling steps 1-4 for each.
Step 5 already queries both indexes internally.
"""

import sys

import config
import step1_create_index
import step2_create_datasource
import step3_create_skillset
import step4_create_indexer
import step5_query_and_rag


def run_setup():
    config.print_config()

    for i, idx_cfg in enumerate(config.INDEXES, 1):
        print(f"\n{'=' * 60}")
        print(f"SETTING UP INDEX {i}/{len(config.INDEXES)}: {idx_cfg.index_name}")
        print(f"Container: {idx_cfg.container_name}")
        print(f"{'=' * 60}")

        step1_create_index.run(idx_cfg)
        step2_create_datasource.run(idx_cfg)
        step3_create_skillset.run(idx_cfg)
        step4_create_indexer.run(idx_cfg)

    print(f"\n{'=' * 60}")
    print(f"SETUP COMPLETE — {len(config.INDEXES)} indexes ready for queries")
    print(f"{'=' * 60}")


def run_reindex():
    for idx_cfg in config.INDEXES:
        print(f"\n  Re-indexing: {idx_cfg.index_name}")
        step4_create_indexer.reset_and_run_indexer(idx_cfg)
        step4_create_indexer.wait_for_indexer(idx_cfg, timeout_seconds=300)


def main():
    args = set(sys.argv[1:])

    if "--query" in args:
        step5_query_and_rag.run()
    elif "--setup" in args:
        run_setup()
    elif "--reindex" in args:
        run_reindex()
    else:
        run_setup()
        print("\n" + "=" * 60)
        print("Starting interactive mode (searches both indexes)...")
        print("=" * 60)
        step5_query_and_rag.run()


if __name__ == "__main__":
    main()
