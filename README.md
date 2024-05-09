# 我的个人微信公众号

- [x] 由 Gemini 提供 AI 能力支持，可以使用图片+文字的方式进行对话。
- [x] 支持 API 创建二维码，用户微信扫码后 HTTP 回调到指定 URL

## 部署方式

`git clone https://github.com/abersheeran/mywxmp` 之后，在项目根目录下创建 `.env` 文件，内容如下：

```.env
# 设置的公众号 Token
WECHAT_TOKEN=
# 公众号 AppID 和 AppSecret
APP_ID=
APP_SECRET=
# 设置的公众号微信号
WECHAT_ID=
# 这是可选的，调用创建二维码 API 时使用的鉴权 TOKEN，默认为空字符串
QRCODE_API_TOKEN=""
# Gemini 服务的 API Key
GEMINI_PRO_KEY=
# 这两个可选，如果你的服务器 IP 本身就可以直连 Gemini 服务，那么可以不用配置
GEMINI_PRO_URL=https://gemini.proxy/v1beta/models/gemini-pro:generateContent
GEMINI_PRO_VISION_URL=https://gemini.proxy/v1beta/models/gemini-pro-vision:generateContent
```

然后运行 `docker compose up --build -d`，本服务将运行在 `6576` 端口。
