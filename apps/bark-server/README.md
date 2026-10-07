# Bark Server

https://bark.day.app/

A privacy-focused, secure, and controllable customizable notification push tool.

## 🧊 最新完整文档（DOC）

[最新完整文档（DOC）](https://bark.day.app/#/?id=bark)

## 🍜 使用运行教程

### docker 运行
1. 拉取镜像
```sh
docker pull finab/bark-server
```

2. 直接下载运行
```sh
docker run -dt \
    --name bark \
    -p 8080:8080 \
    -v `pwd`/bark-data:/data \
    finab/bark-server
```