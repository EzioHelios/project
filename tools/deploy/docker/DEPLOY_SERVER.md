# Warehouse Carbon 服务器部署说明

这套文件面向**服务器环境**，和本地开发使用的
`/Users/eziohelios/Dev/litestar-fullstack/tools/deploy/docker/docker-compose.yml`
分开。

## 文件说明

- `docker-compose.server.yml`
  - 服务器用 compose
  - 不暴露数据库和 Redis
  - 不包含 Mailpit
  - App 只绑定 `127.0.0.1:18100`
- `.env.server.example`
  - 服务器环境变量模板
- `nginx.warehouse-carbon.conf.example`
  - Nginx 反向代理示例

## 一、准备环境变量

在服务器项目目录下执行：

```bash
cd /path/to/litestar-fullstack/tools/deploy/docker
cp .env.server.example .env.server
```

至少修改这些值：

- `APP_IMAGE`
- `SECRET_KEY`
- `APP_URL`
- `DATABASE_PASSWORD`
- `ALLOWED_CORS_ORIGINS`

## 二、登录镜像仓库

```bash
docker login registry.xzzandzyc.store:5000
```

## 三、启动服务

进入项目根目录：

```bash
cd /path/to/litestar-fullstack
```

拉镜像：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server pull
```

启动：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server up -d
```

查看状态：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server ps
```

查看日志：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server logs -f app
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server logs -f worker
```

## 四、更新发布

如果你已经推送了新镜像：

```bash
cd /path/to/litestar-fullstack
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server pull
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server up -d
```

如果要锁定某个 tag，修改 `.env.server` 里的：

```bash
APP_IMAGE=registry.xzzandzyc.store:5000/project/warehouse-carbon:<tag>
```

## 五、Nginx 配置

把下面文件复制到服务器 Nginx 配置目录：

- `/Users/eziohelios/Dev/litestar-fullstack/tools/deploy/docker/nginx.warehouse-carbon.conf.example`

然后改：

- `warehouse-carbon.example.com`
- 证书路径

测试并重载：

```bash
nginx -t
systemctl reload nginx
```

## 六、验证

本机访问：

```bash
curl -I http://127.0.0.1:18100
```

域名访问：

```bash
curl -I https://warehouse-carbon.example.com
```

## 七、常用命令

停止：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server down
```

停止但保留数据卷：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server down
```

停止并删除数据卷：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server down -v
```

重启 App：

```bash
docker compose -f tools/deploy/docker/docker-compose.server.yml --env-file tools/deploy/docker/.env.server restart app
```
