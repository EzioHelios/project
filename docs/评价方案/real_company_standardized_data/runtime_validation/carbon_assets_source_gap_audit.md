# 四租户碳资产真实来源缺口扫描

生成时间：2026-06-13T23:52:16.492Z

## 判定口径

- 扫描对象：`_aggregate/source_files.csv` 附件索引，以及 `evidence_archive/<enterprise_code>/` 已归档证据文件名。
- 扫描范围仅限文件名和索引路径，不解析 PDF/图片/压缩包正文；它用于形成可复跑的缺口证据，不替代人工逐份审阅。
- `asset_ledger_candidate` 表示文件名或路径命中配额、CCER、交易、清缴、履约、登记簿等碳资产台账关键词，需要人工复核。
- `general_carbon_candidate` 只表示命中碳核算、足迹、盘查、GHG、ISO 等一般能碳资料关键词，不足以证明存在真实碳资产台账。
- 若企业只有 `general_carbon_candidate` 或 `no_asset_keyword_hit`，则当前不能把 `/carbon/assets` 计入真实资产数据完整录入。

## 租户结论

| 企业 | 租户 | 资产台账候选 | 一般能碳候选 | 结论 |
| --- | --- | ---: | ---: | --- |
| 本田金属技术(佛山)有限公司 | `fs-honda-metal-2025` | 0 | 12 | 未发现真实配额、CCER、交易、清缴或履约台账文件名候选，维持 `simulation_only`。 |
| 鸿通科技（厦门）有限公司 | `xm-hongtong-2025` | 0 | 10 | 未发现真实配额、CCER、交易、清缴或履约台账文件名候选，维持 `simulation_only`。 |
| 上海马陆日用友捷汽车电气有限公司 | `sh-malu-youjie-2025` | 0 | 15 | 未发现真实配额、CCER、交易、清缴或履约台账文件名候选，维持 `simulation_only`。 |
| 宁波迈柏科技股份有限公司 | `nb-maibo-2025` | 0 | 6 | 未发现真实配额、CCER、交易、清缴或履约台账文件名候选，维持 `simulation_only`。 |

## 命中明细

| 企业 | 来源 | 文件 | 类别 | 关键词 | 相关性 |
| --- | --- | --- | --- | --- | --- |
| 本田金属技术(佛山)有限公司 | source_files_index | 本田金属技术(佛山)有限公司（LAN-2003007475）-碳排放报告.pdf | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 本田金属技术(佛山)有限公司（LAN-2003007475）-碳排放清册.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/2025年水电气数据凭证/HFF 2025年 1-3月水电气凭证.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/2025年水电气数据凭证/HFF 2025年 10-12月水电气凭证.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/2025年水电气数据凭证/HFF 2025年4-6月水电气凭证.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/2025年水电气数据凭证/HFF 2025年7-9月水电气凭证.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/副本理想产品能源消耗统计表（2025年）(1).xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/理想产品2025年产量.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/理想产品比例计算.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | source_files_index | 碳排放资料/理想关联固废2025年产量.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | evidence_archive_file_name | honda_54d2263f9a2b-本田金属技术(佛山)有限公司（LAN-2003007475）-碳排放清册.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 本田金属技术(佛山)有限公司 | evidence_archive_file_name | honda_fa59fd3ea8f6-本田金属技术(佛山)有限公司（LAN-2003007475）-碳排放报告.pdf | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | source_files_index | LVG-GHG-LX-R2604013-2-鸿通科技（厦门）有限公司-第三方核查报告.pdf | `general_carbon_candidate` | GHG | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | source_files_index | 鸿通科技（厦门）有限公司-佐证材料/LAJ-70030020降碳基准值.jpg | `general_carbon_candidate` | 碳 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | source_files_index | 鸿通科技（厦门）有限公司-佐证材料/W01-70030020降碳基准值.jpg | `general_carbon_candidate` | 碳 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | source_files_index | 鸿通科技（厦门）有限公司-碳排放报告.pdf | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | source_files_index | 鸿通科技（厦门）有限公司-碳排放清册.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | evidence_archive_file_name | hongtong_0e6156b29266-LAJ-70030020降碳基准值.jpg | `general_carbon_candidate` | 碳 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | evidence_archive_file_name | hongtong_bc4a491f0e6e-LVG-GHG-LX-R2604013-2-鸿通科技（厦门）有限公司-第三方核查报告.pdf | `general_carbon_candidate` | GHG | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | evidence_archive_file_name | hongtong_da9f3a36a062-鸿通科技（厦门）有限公司-碳排放报告.pdf | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | evidence_archive_file_name | hongtong_db25660a20b9-W01-70030020降碳基准值.jpg | `general_carbon_candidate` | 碳 | not_asset_ledger |
| 鸿通科技（厦门）有限公司 | evidence_archive_file_name | hongtong_f756df8ca6bc-鸿通科技（厦门）有限公司-碳排放清册.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 1534上海马陆日用友捷汽车电气有限公司-碳排放报告.pdf | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 1534上海马陆日用友捷汽车电气有限公司-碳排放清册.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/1.企业基础资料.docx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/2.产品基础信息.docx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/3.场外运输阶段资料.xlsx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/4.生产阶段资料.docx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/5.场内运输阶段资料.xlsx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/6.存储阶段资料.xlsx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/7.包材资料.xlsx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/8.废料处理阶段资料.pdf | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534产品碳足迹数据收集清单/8.废料处理阶段资料.xlsx | `general_carbon_candidate` | 碳;足迹 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | source_files_index | 上海马陆日用友捷汽车电气有限公司-佐证材料/1534降碳基准值.png | `general_carbon_candidate` | 碳 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | evidence_archive_file_name | malu_13a5f2cbf7a8-1534上海马陆日用友捷汽车电气有限公司-碳排放报告.pdf | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | evidence_archive_file_name | malu_4b4b4a0d5ac4-1534上海马陆日用友捷汽车电气有限公司-碳排放清册.xlsx | `general_carbon_candidate` | 碳;排放 | not_asset_ledger |
| 上海马陆日用友捷汽车电气有限公司 | evidence_archive_file_name | malu_c3eed5c1ae74-1534降碳基准值.png | `general_carbon_candidate` | 碳 | not_asset_ledger |
| 宁波迈柏科技股份有限公司 | source_files_index | 杭州万泰认证有限公司资质证书-14064-1.pdf | `general_carbon_candidate` | 14064 | not_asset_ledger |
| 宁波迈柏科技股份有限公司 | source_files_index | 理想供应链产品碳排放盘查报告 --- 宁波迈柏科技股份有限公司--- X02-20040025带支架分配阀V2.pdf | `general_carbon_candidate` | 碳;排放;盘查 | not_asset_ledger |
| 宁波迈柏科技股份有限公司 | source_files_index | 迈柏碳核算Excel总表.xlsx | `general_carbon_candidate` | 碳;核算 | not_asset_ledger |
| 宁波迈柏科技股份有限公司 | evidence_archive_file_name | maibo_7449130e8473-迈柏碳核算Excel总表.xlsx | `general_carbon_candidate` | 碳;核算 | not_asset_ledger |
| 宁波迈柏科技股份有限公司 | evidence_archive_file_name | maibo_a82733d8f2b7-杭州万泰认证有限公司资质证书-14064-1.pdf | `general_carbon_candidate` | 14064 | not_asset_ledger |
| 宁波迈柏科技股份有限公司 | evidence_archive_file_name | maibo_de95f3493271-理想供应链产品碳排放盘查报告 --- 宁波迈柏科技股份有限公司--- X02-20040025带支架分配阀V2.pdf | `general_carbon_candidate` | 碳;排放;盘查 | not_asset_ledger |
