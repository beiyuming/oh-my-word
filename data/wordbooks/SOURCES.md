# 词库来源

本目录保存应用内置和本地导入词库。学习进度、FSRS 状态和复习日志不保存在这些 JSON 文件中，而是保存在 `storage/oh_my_word.sqlite3`。

## `zz_kaoyan_enriched.json`

- 基准词表来源：https://github.com/exam-data/NETEMVocabulary
- 基准原始文件：https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json
- 基准许可证：CC BY-NC-SA 4.0
- 增强内容来源：https://github.com/KyleBing/english-vocabulary
- 增强使用文件：`json_original/json-sentence/KaoYan_1.json`、`KaoYan_2.json`、`KaoYan_3.json`
- IPA 补充来源：https://github.com/open-dict-data/ipa-dict
- IPA 数据许可证：MIT
- 范围：以 NETEM 5528 词为完整基准，只保留 `zz_kaoyan_enriched.json` 作为当前默认内置词库。
- 补全规则：
  - Kyle 源中存在的词，优先使用其音标、词性、中文释义和例句。
  - Kyle 源缺失的词，使用 NETEM 中文释义，并用 open-dict-data/ipa-dict 补 IPA。
  - 上游没有真实例句的词，使用本地生成的考研阅读语境例句和中文翻译，避免空字段或占位字段。
- 注意：KyleBing/english-vocabulary 仓库未见明确 LICENSE 文件；不要把本文件用于商业分发或公开发布包的默认内置词库，除非重新确认授权。

生成命令：

```powershell
py -3.11 scripts/build_kaoyan_enriched.py
```
