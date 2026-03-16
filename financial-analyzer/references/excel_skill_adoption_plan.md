# 专业 Excel 生成技能引入计划

## 1. 目标

为 Soul 对外交付引入独立的专业 Excel 生成技能，实现：

- 金融/咨询风格排版
- 模板化批量生成
- 与分析逻辑解耦（数据与样式分离）

## 2. 选型标准

1. 支持模板驱动（而非硬编码格式）
2. 支持多 Sheet 统一样式
3. 支持图表与条件格式
4. 支持中文字体与 UTF-8 路径
5. 支持字段缺失时降级渲染

## 3. 接口约定

Excel 生成技能输入建议：

```json
{
  "template_version": "soul_v1",
  "entity_id": "issuer_xxx",
  "period": "2024",
  "core_data": {},
  "ext_data": {},
  "evidence_index": []
}
```

输出：
- `financial_output.xlsx`（Soul 成品）

## 4. 落地方式

1. 在技能目录中安装并注册 `excel-generator`（暂定名）。
2. 在 Financial Analysis 主流程增加导出阶段适配层。
3. 通过 `template_version` 控制模板演进与兼容。

## 5. 当前状态

当前环境访问外部 curated skill 仓库受限（网络隧道 403），需在网络可用时执行自动安装；
在此之前先按本规范保留接口，确保后续可以无缝接入。

