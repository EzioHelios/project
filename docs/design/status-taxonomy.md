# Backend Admin Status Taxonomy

The status language must be shared across carbon accounting, energy operations, reference data, and system administration.

## Operational Status

| Token | Chinese label | Meaning | Visual intent |
| --- | --- | --- | --- |
| `draft` | 草稿 | Created but not submitted or not ready for calculation. | Neutral outline. |
| `pending` | 待处理 | Waiting for review, sync, or operator action. | Amber. |
| `in_progress` | 处理中 | Job or workflow is running. | Blue. |
| `approved` | 已通过 | Review passed or record accepted. | Green. |
| `locked` | 已锁定 | Accounting result or reference snapshot cannot be edited casually. | Slate. |
| `rejected` | 已驳回 | Review failed and requires correction. | Red. |
| `archived` | 已归档 | Historical and normally read-only. | Muted. |
| `inactive` | 停用 | Disabled configuration or equipment. | Muted outline. |

## Data Quality Status

| Token | Chinese label | Meaning |
| --- | --- | --- |
| `A` | A 级 | Direct measurement, reliable source, reviewed. |
| `B` | B 级 | System record or validated import, minor assumptions. |
| `C` | C 级 | Manual fill or partial evidence. |
| `D` | D 级 | Estimated, missing supporting data, or needs review. |
| `E` | E 级 | Invalid or not usable for final accounting. |

## Scope Tokens

| Token | Chinese label | Use |
| --- | --- | --- |
| `scope1` | 范围 1 | Direct emissions from owned or controlled sources. |
| `scope2` | 范围 2 | Purchased electricity, heat, steam, or cooling. |
| `scope3` | 范围 3 | Other indirect emissions. |

## Implementation Rule

Business pages should render these states through `src/js/web/src/components/admin-ui/status-badge.tsx`.
Do not hardcode new status colors in page components.
