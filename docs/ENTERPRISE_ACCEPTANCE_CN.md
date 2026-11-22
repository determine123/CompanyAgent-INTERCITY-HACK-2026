# 企业试点交付与验收

| 工作 | 执行人与验收证据 | 放行范围 |
|---|---|---|
| 红豆库存 | 数据负责人明确租户、只读路由与档期。网络管理员在获批出口运行探针。媒介人员按同一查询时刻对照供应商界面，记录公交和地铁各自的可用、占用、锁位、空结果及分页差异。 | 审签字段字典和差异记录后，仅开放已核准的媒体与档期。 |
| 私有部署 | IT 接入企业 IdP、PostgreSQL 与租户策略。两个测试租户分别检查查询、导出、后台任务。管理员轮换服务密钥，核对审计事件，在隔离库恢复备份，记录恢复耗时和数据丢失窗口，交由运维对照业务目标验收。 | 业务、运维与安全负责人签署影子试运行范围、回滚负责人和停用条件。 |
| 降本 | 业务负责人按相同范围登记配对案例及交付质量，财务核对工时费率、模型账单、基础设施和实施分摊，独立审核人复核返工与异常案例。 | 签字报告限定试点期间、样本、成本口径和质量表现。 |

在仓库根目录运行。真实样本、映射和台账保存在企业受控目录。

- 库存字段检查：`python -m scripts.review_hongdou_fixture bus /private/fixture.json /private/mapping.json`。地铁使用 metro。映射 JSON 的键为 resource_id、media_name、reported_units、stock_status，值填供应商字段名。输出只表明非空样本的结构检查结果。
- 生产门禁材料检查：`python scripts/review_migration_gates.py /private/manifest.json`，模板见 deploy/approval-manifest.example.json。生产仍需完成上表所列系统接入和实地演练。
- 工时与成本：`python -m scripts.evaluate_enterprise_pilot /private/trials.json`。沿用原 trials 格式，可在同级添加 costs_cny_fen 对象，以每个 case_id 为键。每案填写 manual_labor、manual_other、assisted_labor、model、infrastructure、rollout_allocation、assisted_other 七项非负人民币分整数。人工包含审核、交接和返工。财务按同一期间分摊固定成本，每项只归集一次。零费用须有依据。
- 样本成本变化率按（人工流程总成本 − 辅助流程总成本）/ 人工流程总成本计算。负值代表成本增加。工时的 bootstrap 区间仅适用于工时。成本汇总和审核签字分别留档。
