# donkey_dbt

The dbt project of the [Amsterdam Bike Share ELT](../README.md) pipeline. It
turns the raw GBFS tables that dlt loads into `donkey_raw` into staging views
and incremental mart tables for Looker Studio.

**Docs:** [models, column descriptions and lineage graph](https://ozcan-ozgur.github.io/amsterdam-bikeshare-elt/)
(published by CI on every push to `main`).

For the architecture, the dashboard and what the data looks like, see the
[root README](../README.md).

## Layers

| Layer | Path | Materialization | What happens here |
|---|---|---|---|
| sources | `models/staging/_sources.yml` | – | raw tables in `donkey_raw`, loaded by dlt |
| staging | `models/staging/` | view | one model per source table: rename, cast, add `snapshot_at`. No joins, no business logic. |
| marts | `models/marts/` | incremental table | business logic and joins. Looker Studio reads these. |

The marts process only snapshots newer than the latest `snapshot_at` in the
table. See [Incremental marts](../README.md#incremental-marts) in the root
README for the semantics.

## Conventions

- Model names: `stg__<entity>` for staging, `fct__<entity>` for marts (double
  underscore).
- YAML files: `_sources.yml` and `_<layer>_models.yaml`. The leading underscore
  keeps them at the top of the folder.
- Every model and column has a description. `persist_docs` also writes them to
  BigQuery as table and column descriptions.
- SQL is linted with SQLFluff (dbt templater, DuckDB dialect, see `.sqlfluff`).
- Keep SQL portable between DuckDB and BigQuery: use `dbt_utils` macros or
  standard SQL, and put BigQuery-only configs behind
  `if target.type == 'bigquery' else none`.

## Targets

`profiles.yml` is in the repo because it holds no secrets.

| Target | Warehouse | Used by |
|---|---|---|
| `dev` (default) | DuckDB at `../donkey.duckdb` (override with `DUCKDB_PATH`) | local runs, CI |
| `prod` | BigQuery dataset `donkey_dbt` (OAuth / ADC) | Cloud Run Job, selected with `DBT_TARGET=prod` |

`prod` caps every query at 1 GB billed (`maximum_bytes_billed`).

## Common commands

Run from this folder, after loading data with `uv run python donkey_pipeline.py`
in the repo root.

```bash
uv run dbt deps                                     # install packages
uv run dbt build --exclude-resource-type unit_test  # models + data tests
uv run dbt test --select test_type:unit             # unit tests (after the build)
uv run dbt docs generate && uv run dbt docs serve   # browse the docs locally
uv run sqlfluff lint models                         # lint SQL
```

Run unit tests after the build: the incremental unit test reads the column
types of the existing mart table, so the table must exist.

`uv run dbt build --full-refresh` rebuilds the marts from the raw tables. It
overwrites the historical station attributes (name, capacity, coordinates) with
the current ones, so use it only when the schema or logic changes.

## Tests

- **Data tests** check the data: `not_null`, `unique`,
  `dbt_utils.unique_combination_of_columns` and `dbt_utils.accepted_range` on
  staging and mart models. They run on every production run. The test for
  occupancy above 100% has `warn` severity.
- **Unit tests** check the SQL logic with fixed inputs. They run in CI only.
  - `test_incremental_only_new_snaphots`: an incremental run processes only
    snapshots newer than the existing table.
  - `test_fleet_snapshot_null_flags`: NULL `is_disabled` / `is_reserved`
    count as false, and vehicles at unlisted stations are counted.

## Packages

| Package | Used for |
|---|---|
| [dbt_utils](https://hub.getdbt.com/dbt-labs/dbt_utils/latest/) | `unique_combination_of_columns`, `accepted_range`, `safe_divide` |
| [codegen](https://hub.getdbt.com/dbt-labs/codegen/latest/) | generating staging model and unit test skeletons |
