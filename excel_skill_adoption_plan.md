# 专业 Excel 生成技能引入计划（2026-03 更新）

## 1. 当前结论

- 现已确认外部网络可用。
- curated skill 中存在直接相关的 `spreadsheet` 技能，且已安装到本地：`/Users/yetim/.codex/skills/spreadsheet`。
- 该技能适合作为 Soul 的 Excel 生成层，但它只解决“怎么专业地生成 Excel”，不替代“Excel 应该长什么样”的结构设计工作。

备注：根据 skill-installer 的约定，安装后通常需要重启 Codex 才能在后续会话中自动发现新技能。

## 2. 能力判断

`spreadsheet` skill 当前覆盖的关键能力包括：

- `.xlsx/.csv/.tsv` 创建、编辑、分析、格式化
- 公式优先而非硬编码结果
- `openpyxl` / `pandas` 工作流
- 图表、条件格式、批注、结构化表格
- 交付前渲染检查建议
- 公式链路保留与原始输入溯源，适合把“原始数据 -> 公式 -> 结果”做成可审计工作簿

这与 Soul 的诉求是匹配的，尤其适合：

1. 多 Sheet 的统一样式控制
2. 金融风格数字格式与条件格式
3. 指标计算公式写入
4. 原始输入批注溯源
5. 后续模板化量产

## 3. 工具分工建议

### `openpyxl`

适合：

- 读取或修改已有 `.xlsx`
- 保留既有样式后继续填充
- 写入批注、命名单元格样式、冻结窗格
- 在既有模板上做轻量后处理

### `XlsxWriter`

适合：

- 从零生成高完成度工作簿
- 图表、条件格式、注释、格式对象体系
- 更明确地控制新工作簿的版式与图表

限制：

- 官方 FAQ 明确说明它不能读取或修改既有 Excel 文件，只能写新文件。

## 4. Soul 的推荐技术路线

### 阶段一：结构先行

- 先按案例分析结果锁定 Soul 的“固定骨架 + 可选模块”。
- 这一阶段不急于把所有案例统一成同一套 Sheet 数量。

### 阶段二：新模板导出

- 优先从稳定 JSON 契约生成新的 Soul 工作簿。
- 这一路线更适合 `XlsxWriter` 风格的“从零生成”方案。

### 阶段三：精修与兼容

- 如需在既有模板上增量填充，或保留人工美化过的老模板，再用 `openpyxl` 做后处理。

## 5. 接口约定（建议）

```json
{
  "template_version": "soul_v1_1_alpha",
  "entity_profile": {},
  "kpi_dashboard": {},
  "financial_summary": {},
  "debt_profile": {},
  "liquidity_and_covenants": {},
  "optional_modules": [],
  "evidence_index": []
}
```

输出：

- `financial_output.xlsx` 或后续正式命名的 `soul_output.xlsx`

## 6. 为什么现在不建议只用一个库硬顶到底

如果只用 `openpyxl`：

- 可以做出可用结果，但从零搭建专业图表和版式时效率一般。

如果只用 `XlsxWriter`：

- 新建工作簿很好，但不适合修改已有案例模板或保留既有样式。

因此更稳妥的方案是：

- Soul 成品导出以“新建模板工作簿”为主
- 需要保留旧模板时再引入 `openpyxl` 后处理

## 7. 当前环境限制

- 本机未发现 `soffice`，暂时不能按 `spreadsheet` skill 建议自动把 Excel 渲染成 PDF/图片做交付前视觉检查。
- 这意味着现阶段仍需在 Excel 本地打开复核版式，或后续补装 LibreOffice 再接入自动渲染检查。

## 8. 下一步落地建议

1. 以 4 个现有案例为样本，先固化 Soul 核心骨架。
2. 选 2 个差异较大的案例做 v1.1-alpha 模板打样。
3. 将 Financial Analysis 的导出阶段改为“先输出稳定 JSON，再由 Spreadsheet Skill 生成 Excel”。
4. 导出时把计算型指标统一要求为公式结果，必要时使用隐藏原始输入层承接溯源。
5. 最后再决定是否保留完整三表和同业对比作为默认模块。
