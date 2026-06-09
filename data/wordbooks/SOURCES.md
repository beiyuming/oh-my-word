# 词库来源

本目录保存应用内置和本地导入词库。学习进度、FSRS 状态和复习日志不保存在这些 JSON 文件中，而是保存在 `storage/oh_my_word.sqlite3`。

## `kaoyan_full.json`

- 来源：https://github.com/exam-data/NETEMVocabulary
- 原始文件：https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json
- 许可证：CC BY-NC-SA 4.0
- 用途：当前项目的考研词表基准，主要提供单词和中文释义。

## `zz_kaoyan_enriched.json`

- 内容来源：https://github.com/KyleBing/english-vocabulary
- 使用文件：`json_original/json-sentence/KaoYan_1.json`、`KaoYan_2.json`、`KaoYan_3.json`
- 范围过滤：
  - 保留已存在于 `kaoyan_full.json` 的单词。
  - 同时保留出现在 https://github.com/ismartcoding/endict 的 `vocabulary/kaoyan.json` 中的单词。
- 用途：个人使用的默认增强覆盖层，提供音标、词性、中文释义和例句。
- 注意：该仓库未见明确 LICENSE 文件；不要把本文件用于商业分发或公开发布包的默认内置词库，除非重新确认授权。

生成命令：

```powershell
py -3.11 scripts/build_kaoyan_enriched.py
```
