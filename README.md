# oh my word (Python)

一个 Windows-first 的 `oh my word` Python 便携重写版，技术栈为 `Python + PySide6`。

## 范围

- 系统托盘优先
- 两种展示模式：`card` 和 `barrage`
- 离线发音优先
- 本地 JSON 设置与 SQLite 学习状态
- 基于目录的词库，内置考研词库
- 支持用户导入 JSON/CSV 词库，并可选下载推荐的 NETEM 词库
- 使用 FSRS 管理复习间隔和 stability/difficulty 字段
- 支持“稍后”跳过当前词，以及托盘“暂停 30 分钟”

## 目录结构

```text
main.py
app/
data/wordbooks/
storage/
build/build_exe.ps1
tests/
requirements.txt
```

## 从源码运行

1. 如有需要，先创建虚拟环境。
2. 安装依赖：

```powershell
py -3.11 -m pip install -r requirements.txt
```

3. 启动应用：

```powershell
py -3.11 main.py
```

应用会从系统托盘启动。首次启动会创建缺失的运行文件，并打开设置窗口。

## 默认热键

- `Ctrl+Alt+1`：朗读当前单词
- `Ctrl+Alt+2`：切换弹窗详情
- `Ctrl+Alt+3`：立即触发下一个单词
- `Ctrl+Alt+4`：将当前单词标记为已掌握

热键可在设置中修改：点击快捷键输入框后按下目标组合键即可。

## 运行期文件

- `storage/settings.json`
- `storage/learning_state.json`
- `storage/oh_my_word.sqlite3`
- `storage/app.log`

源码运行时，`storage/` 位于项目根目录；portable 或安装版运行时，`storage/` 位于 `oh-my-word-py.exe` 同级目录。

`settings.json` 只保存用户配置。`oh_my_word.sqlite3` 保存卡片学习状态、近期单词、FSRS 载荷、复习日志、稍后状态和全局暂停状态。`learning_state.json` 是旧版学习状态文件；如果存在，应用会在启动时兼容导入，不会删除它。

## 词库

应用会按文件名顺序加载 `data/wordbooks/` 下的所有 JSON 文件。

- 后加载文件会覆盖更早文件中的重复单词。
- 损坏的 JSON 文件会被跳过并写入日志。
- 如果没有可用词库，应用会重新创建默认的 `kaoyan_core.json`。
- `zz_kaoyan_enriched.json` 是个人使用的考研增强覆盖层，提供音标和例句；来源见 `data/wordbooks/SOURCES.md`。
- 设置页可以导入本地 JSON 或 CSV 词库，并转换为应用的本地 JSON 格式。
- 设置页可以在确认弹窗后下载推荐 NETEM 词库；确认弹窗会显示来源、许可证和目标路径。

每个词条使用以下形状：

```json
{
  "word": "abandon",
  "ipa": "/əˈbændən/",
  "part_of_speech": "verb",
  "definitions": ["放弃", "抛弃"],
  "example_sentence": "Many exam takers refuse to abandon their daily review plan.",
  "example_translation": "很多考研学生不会放弃每天的复习计划。"
}
```

导入的 JSON 可以使用上述精确形状，也可以使用常见替代字段，例如 `word`、`term`、`wordHead`、`translation`、`definitions`、`tranCn`，以及嵌套的 `content` 对象。导入的 CSV 文件至少应包含一个单词列（如 `word`、`term` 或类似字段）和一个释义/翻译列。

推荐下载源：

- 来源：`https://github.com/exam-data/NETEMVocabulary`
- 原始数据：`https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json`
- 词库许可证：`CC BY-NC-SA 4.0`
- 本地目标：`data/wordbooks/kaoyan_full.json`

## 测试

运行逻辑测试：

```powershell
py -3.11 -m pytest tests -q
```

当前测试套件主要覆盖：

- 设置规范化与持久化
- SQLite 学习状态、旧 JSON 导入和 FSRS 复习写入
- 词库加载与选择规则
- 调度器纯逻辑

## 构建 EXE

```powershell
.\build\build_exe.ps1
```

该脚本使用 `PyInstaller`，并将打包输出放到 `dist/` 下。

打包产物只内置应用代码和 `data/wordbooks/` 词库，不内置本机 `storage/` 用户运行数据；首次启动时应用会在 exe 同级目录按需创建缺失的运行期文件。

## 构建安装包

```powershell
.\build\build_installer.ps1
```

该脚本会先构建 portable 版本，再生成 `dist/oh-my-word-setup.exe`。安装包提供简单的 Windows 图形界面，允许用户选择安装目录，并可选择创建桌面/开始菜单快捷方式和安装完成后启动应用。

安装器会用安装清单管理应用文件。用户选择已有目录时，安装器不会递归清空整个目录；卸载脚本只删除清单中的应用文件和相关快捷方式。

## 备注

- 当前首版只面向 Windows。
- 全局热键使用 Windows 原生 `RegisterHotKey` API。
- 离线发音优先使用 `QtTextToSpeech`，并回退到任何可用的英语语音。
