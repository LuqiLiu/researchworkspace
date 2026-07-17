# Research Workspace Lite — V1.0 发布候选版复验报告

复验日期：2026-07-17（Asia/Shanghai）  
基线报告：`V1_ACCEPTANCE_REPORT.md`（初验结论：Blocked）  
候选镜像：`research-workspace-web:v1.0.0-rc.1`  
修复提交：`f41e462`、`ff6f4fc`

## 结论

**V1 代码与发布候选版验收通过。** 初验中的 3 个 P0 和 11 个 P1
均已关闭；自动化、PostgreSQL、生产 HTTPS 健康检查、不可变构建、
format-2 备份及隔离恢复演练均已实际验证。

该结论表示仓库可标记为 `v1.0.0-rc.1` 并进入真实服务器上线窗口。
真实域名/DNS、公网证书签发、防火墙、主机重启、异机加密备份和真实
用户验收仍属于部署环境检查，不能由本地隔离环境代替。

## 三轮修复结果

### 第一轮：P0 数据与隐私阻断

- 生产健康检查携带可信 HTTPS 转发头，开启 SSL 重定向后仍可 healthy。
- 科研对象采用版本号、行锁和 HTTP 409 冲突响应，陈旧标签页不再静默覆盖。
- 私人 Project/ProjectMember 从 Django Admin 移除，管理员不获得应用层私稿访问。

### 第二轮：安全与数据完整性

- 默认用户附件配额 512 MiB，上传/公开复制原子计量，删除释放，旧数据迁移回填。
- PDF 同时校验扩展名、MIME 和文件头；外部/PDF 题录清洗、截断和降级。
- HTMX 与 MathJax 精确版本固定，增加 SRI、CORS 和 CSP。
- 停用账号可事务化交接对象、项目、附件、标签、快照和用量，并记录审计事件。

### 第三轮：V1 可迁移与发布闭环

- 支持 Crossref/arXiv 题录、字段级来源与置信度、所有核心字段人工校正。
- 支持个人工作区 ZIP、论文 CSV/BibTeX、公开主页 ZIP。
- Python 依赖精确锁定；Python/PostgreSQL/Caddy 基础镜像使用摘要。
- Web 镜像拒绝 `latest`，升级文档提供应用回滚与不兼容迁移恢复路径。
- format-2 备份绑定源 Compose 项目和数据库；恢复要求 dry-run、明确项目、
  数据库匹配及 `--yes`，跨项目恢复仅由隔离演练显式启用。

## 最终验证证据

| 验证项 | 结果 |
| --- | --- |
| 最终镜像构建 | PASS；`research-workspace-web:v1.0.0-rc.1` |
| Django 全量测试 | PASS；69/69，PostgreSQL，0 skipped |
| Django system check | PASS；0 issues |
| 迁移漂移 | PASS；`No changes detected` |
| 生产 `check --deploy` | PASS（仅 HSTS subdomain/preload 两项策略性警告） |
| HTTPS 重定向开启的 Web | PASS；容器 healthy |
| readiness | PASS；`{"status":"ok","database":"ok"}` |
| Compose 服务模型 | PASS；仅 `db`、`web`、`caddy` |
| Caddy 配置 | PASS；`Valid configuration`，无格式警告 |
| Shell 脚本语法 | PASS；backup/restore/drill/deploy/health/entrypoint |
| format-2 备份 | PASS；数据库、媒体、manifest SHA-256 全部 OK |
| 恢复 dry-run | PASS；项目与数据库身份匹配 |
| 全新隔离栈恢复 | PASS；迁移、Django、存储、用户计数检查通过并自动清理 |

## 上线窗口必须完成

1. 将 `WEB_IMAGE` 设置为本次发布的唯一 commit tag 或 registry digest。
2. 创建一份新的 format-2 生产备份，并复制到加密异机存储。
3. 在真实域名验证 DNS、80/443、证书签发/续期和 5432 不可公网访问。
4. 验证 Docker 开机启动、一次主机重启、日志轮换、磁盘告警和 swap。
5. 由 2–10 名目标用户完成一次私稿、分享、附件、导出和公开撤下的短验收。

以上是部署准入清单，不是未完成的 V1 代码功能。
