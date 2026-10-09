# 说明 
CLIProxyAPI 是一个为 CLI 提供 OpenAI/Gemini/Claude/Codex/Grok 兼容 API 接口的代理服务器。

您可以通过任何与 OpenAI（包括 Responses）、Gemini（包括 Interactions）或 Claude 兼容的客户端或 SDK，以本地方式或多 CLI 账户访问多个提供商。


## 😎 特点
- 为 CLI 模型提供 OpenAI/Gemini/Claude/Codex/Grok 兼容的 API 端点
- 新增 OpenAI Codex（GPT 系列）支持（OAuth 登录）
- 新增 Claude Code 支持（OAuth 登录）
- 新增 Grok Build 支持（OAuth 登录）
- 支持流式、非流式响应，以及受支持场景下的 WebSocket 响应
- 函数调用/工具支持
- 多模态输入（文本、图片）
- 多账户支持与轮询负载均衡（Gemini、OpenAI、Claude、Grok）
- 简单的 CLI 身份验证流程（Gemini、OpenAI、Claude、Grok）
- 支持 Gemini AIStudio API 密钥
- 支持 AI Studio Build 多账户轮询
- 支持 Claude Code 多账户轮询
- 支持 OpenAI Codex 多账户轮询
- 支持 Grok Build 多账户轮询
- 通过配置接入上游 OpenAI 兼容提供商（例如 OpenRouter）
- 可复用的 Go SDK（见 docs/sdk-usage_CN.md）

## 🐳 交流群&社区
Github社区板块：https://github.com/router-for-me/CLIProxyAPI/

## 🍜 使用运行教程

### docker 运行

1. 拉取镜像
```sh
cat > docker-compose.yml <<EOF
services:
  cli-proxy-api:
    image: eceasy/cli-proxy-api:latest
    container_name: cli-proxy-api
    restart: always
    volumes:
      - /data/cliproxyapi/config.yaml:/CLIProxyAPI/config.yaml
      - /data/cliproxyapi/data:/root/.cli-proxy-api
      - /data/cliproxyapi/logs:/CLIProxyAPI/logs
    ports:
      - "8113:8317"
EOF
```

2. 直接下载运行
```sh
docker compose up -d
```


### 其他

[请参考完整文档](https://help.router-for.me/)
