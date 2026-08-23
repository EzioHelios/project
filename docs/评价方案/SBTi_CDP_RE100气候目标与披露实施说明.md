# SBTi、CDP、RE100气候目标与披露实施说明

更新日期：2026-08-23
适用模块：`climate_governance`、`/carbon/climate`

## 1. 领域边界

SBTi、CDP和RE100均属于组织层面的气候目标、环境披露和可再生电力承诺，不属于产品碳足迹。产品碳足迹只可作为Scope 3或CDP相关数据点的上游数据来源。

系统严格区分：

```text
组织温室气体盘查结果
≠ 减排项目的基准线减排量
≠ 可再生电力属性声明
≠ 产品碳足迹结果
```

气候治理模块只读引用已锁定或已完成的组织碳、能源计量、减排项目和证据数据，不回写或抵扣组织碳盘查结果。

## 2. 现行依据

| 框架 | 当前实施版本 | 状态与时间 | 官方来源 | 系统影响 |
|---|---|---|---|---|
| SBTi Corporate Net-Zero Standard | V1.3.1；Near-Term Criteria V5.3.1（2026-04版） | 2026年仍适用；V2.0自2027年Q1开始接受验证，V1.3.1可用至2028-01-31 | [SBTi Corporate Net-Zero Standard](https://sciencebasedtargets.org/corporate-net-zero)、[Corporate Near-Term Criteria](https://files.sciencebasedtargets.org/production/files/SBTi-criteria.pdf) | 规则必须版本化。P0检查Scope 1+2目标覆盖率、Scope 3重要性和目标覆盖率；目标路径属于内部管理轨迹，不表示SBTi验证结论。 |
| CDP Corporate Questionnaire | 2026披露周期 | CDP问卷每年调整，2026采用整合后的企业问卷 | [CDP How to Disclose](https://www.cdp.net/en/disclose/how-to-disclose)、[CDP Question Bank](https://www.cdp.net/en/disclose/question-bank) | 按披露年度冻结问卷版本。P0输出内部数据准备完整度和一致性检查，不生成或预测CDP官方评分。 |
| RE100 Technical Criteria | 2025技术准则、2026报告指南 | 2025技术准则现行；2026报告指南于2026年7月发布 | [RE100 Technical Guidance](https://www.theclimategroup.org/re100/technical-guidance)、[RE100中国实施指南](https://www.theclimategroup.org/re100-china-handbook) | 可再生电力必须建立组织用电分母、市场边界、属性年份、唯一归属、注销和证据检查；碳信用不能计入可再生电力。 |
| GHG Protocol Scope 2 Guidance | 2015现行指南；修订中 | 2025-10至2026-01完成公开咨询，正式新版本尚未替代现行指南 | [Scope 2 Guidance](https://ghgprotocol.org/scope-2-guidance) | 市场法合同工具需满足质量准则。系统保留地点法/市场法口径和凭证唯一归属，不将持有凭证直接等同于有效声明。 |

## 3. P0规则

### 3.1 SBTi

P0采用以下正式检查：

- Scope 1和Scope 2目标覆盖率不低于95%。
- 当相关Scope 3排放占Scope 1、2、3总量40%或以上时，需设置Scope 3目标。
- 近期Scope 3目标覆盖率不低于67%。
- 基准年、目标年、目标边界和Scope 2核算方法必须冻结。

系统展示的年度目标路径采用“基准值到目标值的内部线性管理轨迹”，用于进度管理，不声称是SBTi官方验证路径。

### 3.2 CDP

P0只管理气候披露准备度，分为：治理责任、风险与机遇、战略与转型、温室气体盘查、能源、电力与目标、减排措施、核查与证据。

- 温室气体盘查、能源数据、目标和减排措施由系统自动映射。
- 治理、风险、战略等定性信息由责任人确认。
- 结果名称固定为“内部披露就绪度”，不得称为CDP评分、评级或认证结果。

### 3.3 RE100

P0进度公式：

\[
RE100进度=\frac{通过资格校验且完成唯一归属的可再生电力}{组织边界内适用总用电量}
\]

保守资格检查包括：

- 电量大于0；
- 发电与用电属于一致的市场边界；
- 电力属性年份与报告年度一致；
- 已注销或完成唯一分配；
- 存在合同、证书或注销凭证。

普通碳信用、CCER和未注销绿证不进入RE100合格电量。

## 4. 数据自动跟踪

| 业务结果 | 权威数据源 | 刷新方式 |
|---|---|---|
| SBTi实际排放与Scope结构 | `GhgCalculationRun`、`GhgCalculationResult`、`ReportingPeriod` | 组织碳计算完成后按报告期选择最新运行 |
| CDP盘查与能源指标 | 组织碳结果、`EnergyIntervalFact`、减排项目、盘查报告与证据 | 页面查询实时投影；评估运行冻结快照 |
| RE100总用电 | `EnergyIntervalFact`中的当前电力消费事实 | 按报告年度聚合并换算MWh |
| RE100合格电量 | `RenewableElectricityClaim` | 创建时资格检查，评估时重新汇总 |

`ClimateAssessmentRun`冻结来源运行、规则版本、目标版本、指标和检查结果，后续源数据变化不改变历史评估。

## 5. 产品边界

P0不实现SBTi官方申请、CDP门户提交、CDP官方评分预测、RE100会员申请或外部登记系统同步。系统提供可审计的内部管理和披露准备能力，但不替代官方验证、披露平台或第三方鉴证。
