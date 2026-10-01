# AI Infra 面试题页面与本机采集器

静态页面发布在 `https://jaykay233.github.io/interview-questions/`，网站根页面仍是 ArchAtlas。类别为算子、编译器、通信、框架。当前 `data/questions.json` 为空，是因为尚未在授权的小红书账号下执行本机首次扫码；不会用示例题冒充真实采集结果。

## 数据与隐私

- 采集只使用 Spider_XHS 的公开搜索接口，读取搜索结果中的标题、笔记 ID 和来源链接；不打开笔记详情，不抓评论、用户资料或媒体，也不尝试绕过验证码/风控。
- 页面是可追溯的标题级“题目线索”索引，不镜像笔记正文。若标题/分类不准确，请到来源笔记核对。
- 登录会话保存在 macOS Keychain；Cookie 不进 Git、不传 GitHub Actions。GitHub Actions 只部署本地已经生成的静态 JSON。
- Spider_XHS 是第三方、非官方接口实现，接口与平台规则可能变化。请遵守小红书服务条款；遇到验证/限流就停止。上游仓库没有发现 LICENSE 文件，因此安装脚本会把其代码仅克隆到本机缓存目录，不复制进本仓库。

## 首次配置（Mac）

在网站仓库根目录执行：

```bash
bash scripts/xhs-collector/setup_local.sh
SPIDER_XHS_PATH="$HOME/.local/share/archatlas/Spider_XHS" \
  ./.xhs-venv/bin/python scripts/xhs-collector/collect_questions.py --login
```

按终端提示用小红书 App 扫码。登录和第一次采集成功后，可在 `interview-questions/data/questions.json` 预览结果，然后安装每日 09:00（本机时区）采集并 SSH 推送任务：

```bash
bash scripts/xhs-collector/install_schedule.sh
```

机器需要开机且能联网；SSH key 要能 `git push origin master`。LaunchAgent 日志在 `~/Library/Logs/ArchAtlasXHS/`。手动运行一次：

```bash
bash scripts/xhs-collector/run_daily.sh
```

停止每日任务：`bash scripts/xhs-collector/uninstall_schedule.sh`。如果会话过期，可重新执行 `collect_questions.py --login` 更新 Keychain 登录态。不要把 Cookie 粘贴到聊天、代码或 GitHub Secrets。
