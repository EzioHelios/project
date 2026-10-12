# Warehouse production release, 2026-10-12

## Scope

- Host: Huawei; deployment directory: `/root/warehouse`.
- Public site: https://warehouse.nexlca.com.
- Publish current application, bundled frontend, Cesium runtime and private Anfang/Xiangtai scene packs.
- Create customer username `taizhou`, limited to Anfang and Xiangtai membership. No superuser access.
- No demo installation, warehouse business-data regeneration, AI recognizer startup, broker restart or unrelated nexLCA deployment.

## Source and artifacts

- Application source: `4664ef5` (includes username login, locked runtime dependencies and campus CSP fix).
- Entrypoint: `scripts/build_push_multiarch.sh`, `DOCKERFILE=tools/deploy/docker/Dockerfile`, `PUSH_LATEST=false`.
- Build context: clean `git archive`; unrelated untracked dataset work and local credentials excluded.
- Image: `registry.xzzandzyc.store:5000/project/warehouse-carbon:20261012-taizhou-release-r2`.
- Registry digest: `sha256:593bfb7b8463fe4143f663148f01ab6a83b6044f1fcad90504f33775d679d34e`.
- The warehouse Nginx proxy serves all paths through app port 18100. Frontend and private assets are shipped in the application image; this site does not use a separate fe-release deployment.

## Backup and rollback

- Backup directory: `/root/warehouse/backups/release-20261012-5c36b880`, mode 0700.
- Successful database archive: `warehouse-all-tenants.dump`, 259364046 bytes, mode 0600.
- SHA256: `080f1c5318a5c8655fca0548b647fa29a15f98f078c3fc6c083582a8106d4597`.
- Validated using `pg_restore --list` and full archive decoding to `/dev/null`.
- Administrative backup used the existing tenant-bypass policy with `--enable-row-security`; no RLS policies were removed or disabled.
- An earlier incomplete `warehouse.dump` is not a usable backup.
- Compose and environment snapshots are retained. No credentials are included in this record.
- Previous production image: `registry.xzzandzyc.store:5000/project/warehouse-carbon:f541c825-20260904-energy-demo`, also tagged locally on the server as `warehouse-carbon:rollback-20261012`.
- Rollback application services by restoring the previous APP_IMAGE and recreating only app/worker/mqtt-ingest-worker. Do not restore the entire database or downgrade schema casually; the backup predates customer account creation.

## Database and customer access

- Migrated `f6a7b8c9d0e1` to `f9a0b1c2d3e4`; migration container exited 0.
- `taizhou`: active, verified, non-superuser, MEMBER of exactly these teams:
  - `00000000-0000-7000-8000-000000000002`: 安方中心库.
  - `00000000-0000-7000-8000-000000000001`: 祥泰仓库.
- Dedicated role `warehouse_customer_viewer` grants `carbon.inventory.view`; no additional administrative or calculation permission was granted.
- Credentials are stored separately in the operator's gitignored, mode-0600 local delivery file.

Business record counts before and after migration:

| Team | Areas | Devices | GHG activities | GHG calculation results | GHG inventory reports |
| --- | ---: | ---: | ---: | ---: | ---: |
| 安方中心库 | 11 | 16 | 8 | 8 | 1 |
| 祥泰仓库 | 30 | 20 | 67 | 0 | 0 |

The zero Xiangtai result/report counts were present before this release. This deployment does not claim to fill existing business-data gaps.

## Verification

- Focused authentication tests: 35 passed; scene/material tests: 40 passed; frontend campus tests: 12 passed.
- TypeScript, changed-file Ruff and Biome checks passed.
- Campus CSP regression: 1 passed with focused `--no-cov` execution. The initial focused invocation hit the repository-wide 65% coverage gate; no full-suite coverage claim is made.
- Container startup import succeeds with locked SQLAlchemy 2.0.46.
- Public username login: 201; team list contains exactly two authorized warehouses.
- Both protected scene manifests and all four GLBs: 200; downloaded hashes match tracked source files.
- Both warehouses' overview/power/carbon API responses: 200.
- Foreign team and foreign scene reads: 403; anonymous scene asset read: 401.
- Existing overview endpoint returns an empty 200 for an unauthorized tenant header rather than 403; asserted null/zero KPIs, no flow links, no trends and no area/period choices. It did not return foreign business data. This response convention was not refactored during deployment.
- Final r2 service verification: app, worker and mqtt-ingest-worker run image ID `sha256:8b1dfbd75ac021c27696f3b92a76a57ff361a585d9d020255aaa3db08a7e47c8`, zero restarts. MQTT retry job completed without error; cache and EMQX were not recreated.
- Final r2 public API verification repeated successfully after the CSP fix.
- Built-in browser: short username login succeeded; both tenant models rendered over satellite imagery; top view, entrance walk and forward movement exercised for both warehouses. Switching tenants changes the model and energy figures.
- Browser overview: Anfang shows energy and carbon KPIs; Xiangtai shows energy figures and explicitly shows no carbon calculation result, consistent with the database counts above.
- Evidence is in gitignored `.storage/deploy-20261012/`: `verification.json`, `anfang-model.png`, `anfang-top.png`, `anfang-walk.png`, `xiangtai-model.png`, `xiangtai-top.png`, `xiangtai-walk.png`, `xiangtai-overview.png`.
- Server disk after deployment: 11 GiB free (89% used). No images or volumes were pruned.

## Issues caught before acceptance

1. Runtime wheel install previously resolved unlocked dependencies and fetched an incompatible SQLAlchemy version. It now uses constraints exported from uv.lock.
2. Browser campus rendering was blocked by the existing CSP. Added only the configured Esri imagery origin to image/connect permissions and local `blob:` connections for authenticated GLB rendering. Frame/object restrictions and the existing script policy remain in place.

The material-allocation and vision residual business issues recorded in `material-vision-submit-review-20260921.md` remain outside this release's fixes. No online RTSP publisher or AI-recognition worker was enabled.
