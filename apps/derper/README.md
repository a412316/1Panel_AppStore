# Tailscale Derper

https://tailscale.com

Private WireGuard® networks made easy

## 🧊 最新完整文档（DOC）

[最新完整文档（DOC）](https://tailscale.com/kb/1118/custom-derp-servers/)

## 🍜 使用运行教程

### docker 运行

目录挂载 `-v`，根据自己的需求选择：
|容器目录|说明|
|---|---|
|/var/run/tailscale/tailscaled.sock|Tailscale运行文件|
|/app/certs|SSL证书|

环境变量 `-2`，根据自己的需求选择：
|环境变量|是否为空|说明|默认|
|---|---|---|---|
|DERP_DOMAIN|true|derper server hostname|your-hostname.com
|DERP_CERT_DIR|false|directory to store LetsEncrypt certs(if addr's port is :443)|/app/certs
|DERP_CERT_MODE|false|mode for getting a cert. possible options: manual, letsencrypt|letsencrypt
|DERP_ADDR|false|listening server address|:443
|DERP_STUN|false|also run a STUN server|true
|DERP_HTTP_PORT|false|The port on which to serve HTTP. Set to -1 to disable|80
|DERP_VERIFY_CLIENTS|false	verify clients to this DERP server through a local tailscaled instance|false

1. 拉取镜像
```sh
docker pull fredliang/derper
```

2. 直接下载运行
```sh
docker run \
    -e DERP_DOMAIN=derper.your-domain.com \
    -p 80:80 \
    -p 443:443 \
    -p 3478:3478 \
    fredliang/derper

```