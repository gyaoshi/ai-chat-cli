# 提交前先对一遍

## 这个改动做了什么

<!-- 一句话说清楚。如果修的是 issue，写上 fixes #123 -->

## 类型

- [ ] 修 bug
- [ ] 新功能
- [ ] 文档
- [ ] 站点选择器更新（网页改版了）
- [ ] 重构 / 工程化

## 自查清单

- [ ] `pytest -q` 全绿（含 mock 站点的端到端测试）
- [ ] `ruff check .` 和 `ruff format --check .` 通过
- [ ] 没有把 `browser_profile/`、`output/`、`test_report/`、`python_path.txt` 提交进来
- [ ] 日志和截图里没有我的账号、手机号、cookie
- [ ] 如果改了输出行为，README 的「输出约定」和「退出码」两节也同步更新了
- [ ] 如果改了 `sites.json`，`ai_chat_cli/data/sites.json` 也同步了（有个测试会检查一致性）

## 输出契约提醒

这个工具的核心价值是「stdout 只有回复正文」。任何改动都不能把日志、提示、错误信息写进 stdout ——
脚本靠 `> out.txt` 直接拿干净文本，靠退出码判断成败。
