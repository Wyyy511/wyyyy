# Railway 部署

1. 解压项目；GitHub 仓库根目录直接上传源码，不要只上传 ZIP。
2. Railway → New Project → Deploy from GitHub Repo。
3. Service → Variables 添加：
   - `DEEPSEEK_API_KEY=你的DeepSeek密钥`
   - 可选 `DEEPSEEK_MODEL=deepseek-v4-flash`
   - 可选 `DEEPSEEK_BASE_URL=https://api.deepseek.com`
4. `railway.json` 已配置启动命令：`uvicorn server:app --host 0.0.0.0 --port $PORT`。
5. 部署 Active 后，Settings → Networking → Generate Domain。
6. 先访问 `/api/health`，再访问根网址。

若部署后仍显示旧界面，确认 GitHub 最新 commit 已包含新版 `static/index.html` 与 `static/app.js`，然后在 Railway Redeploy 最新 commit。V5 后端已对 HTML/JS/CSS 设置 no-cache，避免浏览器继续使用旧页面资源。
