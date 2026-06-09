# 词库目录契约

## 范围

本 spec 约束 `app/words.py` 和 `data/wordbooks/`。它定义词库文件格式、加载顺序、导入/下载规则和词条规范化。

## 词库目录

内置和导入词库位于：

```text
data/wordbooks/
```

应用按文件名顺序加载该目录下所有 JSON 文件。

## 当前词条形状

规范化后的词条必须包含：

- `word`
- `ipa`
- `part_of_speech`
- `definitions`
- `example_sentence`
- `example_translation`

`definitions` 必须是非空字符串数组。缺失必填字段的内置词库条目会被跳过并记录 issue。

## 加载与合并

- 损坏 JSON 文件被跳过并记录 issue。
- 根节点不是数组的词库文件被跳过并记录 issue。
- 重复单词按 casefold 后的 `word` 合并。
- 后加载文件覆盖更早文件。
- 如果后加载词条的 IPA 是占位值，而旧词条有更完整 IPA，应保留旧 IPA。
- 如果没有可用词库，应用会重新创建默认 `kaoyan_core.json`。
- 当前仓库默认只保留 `zz_kaoyan_enriched.json` 作为完整考研词库。该文件以 NETEM 5528 词为基准，补充 IPA 和例句；来源、补全规则和授权注意事项记录在 `data/wordbooks/SOURCES.md`。

## 导入

设置页支持导入 JSON 和 CSV。

导入 JSON 可以是数组，也可以是包含 `words`、`data`、`entries`、`items` 数组的对象。导入 CSV 使用 `csv.DictReader`，至少要能解析出单词和释义字段。

导入解析支持常见替代字段，例如：

- 单词：`word`、`term`、`headword`、`wordHead`、`text`。
- 释义：`definitions`、`translation`、`meaning`、`tranCn`、`chinese`。
- 音标：`ipa`、`phonetic`、`pronunciation`、`ukphone`、`usphone`。

导入输出写为应用本地 JSON 词库，不直接写运行期学习状态。

## 推荐下载

推荐考研词库下载源：

- 页面：`https://github.com/exam-data/NETEMVocabulary`
- 原始数据：`https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json`
- 许可证：`CC BY-NC-SA 4.0`
- 本地目标：`data/wordbooks/kaoyan_full.json`

该下载目标是用户可选导入文件。默认仓库可以不跟踪 `kaoyan_full.json`，因为 `zz_kaoyan_enriched.json` 已包含完整基准词表。

下载前必须在 UI 中显示来源、许可证和目标路径，并要求用户确认。

## 与学习状态的边界

词库模块负责内容，不负责复习算法。SQLite 学习状态通过 `word` 与词库内容关联；第一版不要求把完整词条复制进数据库。

## 验证

词库变更必须覆盖：

- 文件排序和重复覆盖。
- 损坏 JSON。
- 无可用词库时恢复默认词库。
- JSON/CSV 导入形状。
- 推荐下载转换和许可证说明。
