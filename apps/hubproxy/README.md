# 说明 
HubProxy 加速服务


## 😎 特点

- 一个轻量级、高性能的多功能代理服务器，专为加速 Docker 镜像、GitHub 文件和 AI 模型下载而设计。它采用 Go 语言构建，为面临网络限制或寻求提升下载速度的开发者提供统一的加速解决方案。

## 🐳 交流群&社区
Github社区板块：https://github.com/sky22333/hubproxy/

## 🍜 使用运行教程

### docker 运行

1. 拉取镜像
```sh
cat > docker-compose.yml <<EOF
version: '3.8'
services:
  hubproxy:
    image: ghcr.io/sky22333/hubproxy
    container_name: hubproxy
    restart: always
    ports:
      - "5000:5000"
    volumes:
      - ./config.toml:/root/config.toml
    logging:
      driver: json-file
      options:
        max-size: "1g"
        max-file: "2"
EOF
```

2. 直接下载运行
```sh
docker compose up -d
```


### 其他

[请参考完整文档](https://zread.ai/sky22333/hubproxy)
