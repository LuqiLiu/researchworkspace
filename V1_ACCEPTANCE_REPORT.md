# Research Workspace Lite — V1 发布候选版验收报告

验收日期：2026-07-17（Asia/Shanghai）  
验收范围：Git、PRD 覆盖、工程与生产配置、权限与隐私、文件上传、科研对象、文献处理、搜索、公开发布、导出、备份恢复、2 GB 资源、依赖与代码质量。  
验收原则：只检查、测试和记录；未修改业务代码、模型或迁移；全部动态测试使用隔离 SQLite、临时 PostgreSQL/媒体卷或内存合成数据。

状态定义：`PASS` 已实际验证且完全满足；`PARTIAL` 仅部分满足；`FAIL` 不满足或存在错误；`NOT TESTED` 当前环境无法安全验证；`NOT APPLICABLE` 明确不适用。

## 1. 执行摘要

| 项目 | 结果 |
| --- | --- |
| 当前版本 | `research-workspace-lite 0.1.0`；建议产品状态为 **V0.9 Release Candidate（Blocked）** |
| 当前 commit | `e38c09dfa67e84462601215d8396262f4300a98a` |
| 当前分支 | `main` |
| 自动化测试总数 | 53 |
| 自动化通过 | 53 |
| 自动化失败 | 0 |
| 自动化跳过/未测试 | 0 |
| 额外验收 | PostgreSQL 权限矩阵、生产健康检查、备份/篡改/恢复、全新栈功能恢复、上传矩阵、搜索、并发编辑、资源采样等；其发现单独计入问题清单，不混入 53 个自动化用例分母 |
| 是否建议定义为正式 V1 | **否** |
| 是否建议立即部署内部试用 | **否；先修复全部 P0。修复后可在接受 P1 限制、可信 2–10 人、严格磁盘监控条件下重新评估内部试用** |
| P0 阻断项 | **3** |
| P1 阻断项 | **11** |
| Git 状态（生成报告前） | 干净；无未提交修改、无未跟踪文件、无 remote |
| 本轮业务代码变更 | **无**；唯一项目文件变更是新增本报告，且未 `git add/commit/push` |

说明：53/53 证明已有测试覆盖的行为稳定，但不能抵消验收中实际复现的生产启动、隐私边界和并发写入问题。

## 2. 总体结论

**D. 存在严重安全或数据风险，应暂停使用。**

当前版本的私有对象查询、站内分享、项目显式共享、附件独立授权、公开快照隔离、备份校验与恢复主体设计是成立的；完整自动化测试也全部通过。然而，以下三项达到用户定义的 P0：

1. 文档要求的生产 HTTPS 配置会使 Web 健康检查持续失败，Caddy 因依赖健康 Web 无法正常启动。
2. 两个标签页或并发自动保存会静默覆盖先保存正文，已实际复现内容丢失。
3. Django Admin 直接暴露私人项目名称、描述和成员内联，并允许通过项目所有者/成员关系绕过应用层隐私边界。

因此当前版本只适合继续隔离开发和修复验证，不应承载真实科研数据，也不能标记为正式 V1。

## 3. PRD 覆盖矩阵

| PRD 模块/要求 | 当前实现 | 验证方式 | 状态 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| Git 与仓库卫生 | 7 个阶段 commit；业务迁移均跟踪；敏感数据忽略 | Git 全量状态、跟踪路径和签名扫描 | PASS | commit `e38c09d`；报告前 porcelain 为空；19 个迁移目录文件（其中 12 个业务迁移版本） | 无 remote，无法验证推送/发布标签 |
| 三服务轻量架构 | `db/web/caddy`，无 Redis/Celery/MinIO/ES/K8s/Node 运行时 | `docker compose -f compose.yml config --services` | PASS | 仅输出 `db web caddy` | 浏览器端依赖外部 CDN，见 P1-09 |
| 生产配置 | DEBUG False、环境变量、Secure Cookie、私网 DB、Caddy 唯一端口入口 | production check、Compose/Caddy 校验、隔离启动 | FAIL | `check --deploy` 仅 2 个可选 HSTS 警告；但 HTTPS=true 时内部健康检查 TLS 超时 | P0-01 |
| 账户与登录 | 管理员创建、用户名/邮箱登录、限流、停用即时失效 | 3 个自动化测试；临时 PostgreSQL 会话补测 | PASS | 停用后旧会话访问受保护页返回 302；停用账号登录失败 | 无所有权转移，见 P1-07；审计覆盖不足见 P2-09 |
| 管理员隐私边界 | 私有 `ResearchObject` 未注册 Admin | Admin 页面只读实测与注册表审阅 | FAIL | 管理员能在项目变更页看到私人项目名称/描述和成员 inline | P0-03 |
| 七类科研对象 | NOTE/PAPER/IDEA/EXPERIMENT/ISSUE/WRITING/RESOURCE | 对七类逐一用表单仅填标题/正文保存 | PASS | 7/7 有效、默认 `PRIVATE`、metadata 初始均 `{}` | 列表过滤和生命周期不完整，见 P2-03/P2-05 |
| Markdown 与编辑 | Markdown 源保存、代码块/表格、清洗、HTMX 自动保存 | 渲染函数、HTTP/表单、并发写入补测 | FAIL | 代码块/表格通过，XSS 标签移除；图片被去除；双标签页后写覆盖 | P0-02、P2-02 |
| 站内分享 | VIEWER/COMMENTER/EDITOR，撤销即时 | 14 个自动化权限测试 + PostgreSQL 合成矩阵 | PASS | 权限等级、旧 URL 刷新、删除/收藏/分享管理均后端拒绝 | 无已发现普通用户绕过 |
| 项目共享 | 仅显式共享对象；MEMBER/EDITOR；退出即时失效 | 自动化 + PostgreSQL 角色补测 | PASS | MEMBER 可评论不可编辑；EDITOR 可编辑不可删除；移除后不可见 | Admin 可操纵成员关系，见 P0-03；项目列表 N+1 见 P2-05 |
| 附件权限 | 正文与附件权限分离；随机路径；下载鉴权 | 自动化、表单矩阵、响应头、Caddy 路径审阅 | PARTIAL | 撤销即时；`attachment` 下载；`nosniff`；随机 UUID | 校验和生命周期仍有缺口，见 P2-06 |
| 用户存储配额 | 单文件上限、默认/个别配额、用量、并发控制 | 模型/表单/服务/管理界面静态审阅 | FAIL | 仅有 50 MB 单文件上限与主机剩余空间检查 | P1-01 |
| DOI/PDF/arXiv 文献处理 | DOI、Crossref、PDF 元数据、查重、BibTeX | 5 个自动化测试；15/40 MB 合成 PDF；异常元数据补测 | PARTIAL | DOI/超时降级/DOI-title-hash 查重/BibTeX 通过；40 MB HTTP 导入 302 成功 | P1-02、P1-03 |
| 搜索 | 私有/分享/项目内容；标题、正文、标签、作者、DOI、项目、评论 | 自动化防泄漏 + 中文/特殊字符/归档补测 | PARTIAL | 中文、标签、项目、评论通过；特殊字符不报错；删除内容不出现 | 文件名、公开快照、分页缺失；归档默认出现，见 P2-04 |
| 公开快照 | 独立记录、白名单、显式附件、撤下、安全扫描 | 10 个自动化测试 + 恢复栈未登录访问 | PASS | 私稿变化不自动同步；撤下 404；公开附件必须确认且复制 | 更新确认和源删除语义需更清晰，见 P2-08 |
| 个人主页 | 个人资料、论文、精选笔记、公开项目摘要 | 模型、表单、模板和未登录访问 | PARTIAL | 姓名/头像/机构/简介/方向/联系/ORCID/Scholar/GitHub/论文/笔记可用 | 软件与数据、CV、独立公开项目结构缺失，见 P2-07 |
| 首页与研究工作台 | PRD 个性化入口和待办 | 路由与模板审阅 | FAIL | 登录后首页直接重定向对象列表 | P2-01 |
| 数据导出 | 单项 Markdown/BibTeX、论文 CSV、个人 ZIP、公开主页导出 | HTTP 补测与 URL/视图审阅 | PARTIAL | Markdown 内容精确、BibTeX 200 | P1-04、P1-05、P1-06；中文文件名见 P2-11 |
| 备份与恢复 | DB+媒体、原子发布、校验和、保留、隔离恢复 | 两次备份、篡改拒绝、同栈恢复、两个全新恢复栈 | PASS | 30 迁移、4 用户、私有/共享/附件/搜索/公开页均恢复；篡改在停服务前拒绝 | 目标保护、备份盘预检和异机仍有缺口 |
| 升级与回滚 | 备份、构建、迁移、健康检查、保留旧版 | 脚本/文档审阅 | PARTIAL | 升级前备份要求明确，部署脚本有检查 | P1-10、P1-11 |
| 2 GB 资源边界 | 容器限额、2 workers、小内存 PG、日志轮换、磁盘检查 | Docker 实测与配置审阅 | PARTIAL | 三服务上限合计约 1.4 GB；实测资源较低 | 精确 PDF 瞬时峰值、真实 2–10 并发、ZIP 不可完整验证 |
| 依赖与代码质量 | Django LTS、轻依赖、统一权限服务、Markdown 清洗 | 编译、测试、扫描、查询计数 | PARTIAL | Django 5.2.16；无 TODO/debug/skipped；业务无原始 SQL | P1-08、P1-09、P2-05 |

Django 5.2 是仍受支持的 LTS，官方扩展支持至 2028 年 4 月，参见 [Django 官方支持版本表](https://www.djangoproject.com/download/)。

## 4. P0 问题

### P0-01 — 文档推荐的 HTTPS 配置使生产栈无法健康启动

- **问题描述**：`DJANGO_SECURE_SSL_REDIRECT=true` 时，容器健康检查访问 `http://127.0.0.1:8000/health/ready/`，被重定向到同端口 HTTPS；Gunicorn 不提供 TLS，最终握手超时。Caddy 又依赖 Web `service_healthy`。
- **影响范围**：按 README/部署文档启动的正式三服务栈；Caddy 启动链路和自动恢复。
- **复现方法**：在隔离项目中使用 `docker compose -f compose.yml up -d db web` 并设置 HTTPS 重定向为 true；健康日志连续返回 `urllib.error.URLError: ... handshake operation timed out`。关闭该设置后 6 秒内 healthy。
- **文件/位置**：`compose.yml:61,84,95,116`；`docs/deployment.md:40`；`README.md:48`。
- **严重程度**：P0（生产无法启动）。
- **修复建议**：健康检查显式发送可信 `X-Forwarded-Proto: https`，或为内部健康端点配置安全的重定向豁免；保留外部 HTTPS 强制，并新增 HTTPS=true 的 Compose 回归测试。
- **是否阻止 V1**：**是；也阻止当前内部部署。**

### P0-02 — 并发编辑/自动保存静默覆盖正文

- **问题描述**：保存请求不携带或校验版本号/`updated_at`。两个标签页读取同一版本后依次保存，后写请求无提示覆盖先写正文。
- **影响范围**：普通编辑、HTMX 自动保存、两标签页、两位 EDITOR 同时编辑、网络延迟后到达的旧请求。
- **复现方法**：对同一对象构造两个旧实例；先保存 `tab one text`，再保存 `tab two stale text`；最终内容为后者，`conflict_detected=False`，先写内容丢失。
- **文件/位置**：`app/research_objects/models.py:71,98`；`app/research_objects/views.py:37-46,190-222`。
- **严重程度**：P0（已复现数据丢失）。
- **修复建议**：引入服务端乐观锁/版本字段或条件更新；冲突返回 409 并保留双方草稿；自动保存显示失败/冲突状态；增加两标签页和乱序请求测试。
- **是否阻止 V1**：**是；也阻止承载真实研究正文的内部试用。**

### P0-03 — Django Admin 暴露私人项目并可操纵成员关系

- **问题描述**：`Project` 注册在 Django Admin，默认变更表单显示项目名称、描述、所有者；`ProjectMemberInline` 可编辑成员。管理员可读取私人项目元数据，并可添加自己为成员或改所有者，从而获得应用层对显式项目共享对象的访问。
- **影响范围**：所有私人项目、项目成员关系、通过项目共享的对象；与管理员操作指南的隐私声明冲突。
- **复现方法**：临时管理员只读访问 `/admin/projects/project/<id>/change/`，结果为 200，私人项目名称、描述及成员 inline 均出现。静态审阅确认表单未设只读/权限限制。
- **文件/位置**：`app/projects/admin.py:6-15`；`docs/admin-operations.md:3-8`。
- **严重程度**：P0（隐私泄漏与权限绕过路径）。
- **修复建议**：从 Admin 移除 Project/ProjectMember，或实现严格的只读最小字段与不可添加/修改/删除权限；增加“管理员不能读取项目字段或改变成员/所有者”的回归测试。
- **是否阻止 V1**：**是；除非所有管理员均被明确视为科研内容受托人，但这与当前 PRD/文档不符。**

## 5. P1 问题

### P1-01 — 用户存储配额完全缺失

- **问题描述**：只有 50 MB 单文件上限和主机剩余空间检查；没有默认用户配额、个别调整、已用空间、超额拒绝或并发原子预留。
- **影响范围**：所有附件/PDF 上传、磁盘容量、2 GB 主机稳定性。
- **复现方法**：审阅用户/附件模型、上传表单、服务和 Admin；未发现 quota/usage 字段或事务锁；`AttachmentForm.max_size` 仅限制单文件。
- **文件/位置**：`app/research_objects/forms.py:105-130`；`app/research_objects/models.py:138-157`；`compose.yml:70`。
- **严重程度**：P1。
- **修复建议**：实现默认配额、按用户覆盖、事务内原子用量预留/回收、用户可见用量和管理员调整；覆盖并发上传测试。
- **是否阻止 V1**：**是**；修复 P0 后可在可信小规模、人工磁盘监控和限制上传的条件下短期内部试用。

### P1-02 — arXiv 与可修正元数据工作流未实现

- **问题描述**：仅有 DOI 正则、PDF 元数据和 Crossref；无 arXiv ID/版本识别，无 arXiv→DOI 演进，无匹配置信度；自动元数据未进入可编辑表单，来源字段会被后写来源覆盖。
- **影响范围**：预印本、会议/期刊来源判断、人工校正和可追溯性。
- **复现方法**：代码库搜索无 arXiv 解析；`ResearchObjectForm` 不包含 `metadata_json`；服务仅定义 DOI_PATTERN。
- **文件/位置**：`app/papers/services.py:17-24,70,82,92,169`；`app/research_objects/forms.py:20-28`。
- **严重程度**：P1（PRD 核心文献流程不完整）。
- **修复建议**：建立分来源字段、来源/置信度记录、arXiv 版本解析与 DOI 关联、用户可编辑元数据及“用户修改不被后台覆盖”规则。
- **是否阻止 V1**：**是**。

### P1-03 — 有效 PDF 的异常长标题导致 500/DataError，未降级保存

- **问题描述**：PDF metadata title 直接作为 240 字符数据库标题；合法 PDF 中 300 字符标题触发 PostgreSQL `DataError`，导入失败。
- **影响范围**：元数据异常或恶意 PDF；文献导入可靠性。
- **复现方法**：用 pypdf 生成一页有效 PDF，`/Title` 为 300 字符；调用导入服务得到 `DataError`，新增对象和附件记录均为 0。
- **文件/位置**：`app/papers/services.py:160-186`；`app/research_objects/models.py:70`。
- **严重程度**：P1。
- **修复建议**：所有外部字符串先归一化、长度限制和可打印字符清洗；解析/数据库错误均回退到文件名或手填标题，并测试异常 metadata。
- **是否阻止 V1**：**是**。

### P1-04 — 个人全部内容 ZIP 导出缺失

- **问题描述**：无个人 ZIP 路由、服务或权限/配额策略。
- **影响范围**：用户迁移、离站备份、数据主权。
- **复现方法**：审阅全部 URL/视图，仅有单对象 Markdown 和单论文 BibTeX。
- **文件/位置**：`app/research_objects/urls.py:8-23`；`app/papers/urls.py:8-9`。
- **严重程度**：P1（验收规则明确指定）。
- **修复建议**：流式 ZIP，包含自有 Markdown、元数据和有权附件；明确分享/删除内容规则并限制资源。
- **是否阻止 V1**：**是**。

### P1-05 — 论文 CSV 导出缺失

- **问题描述**：无论文集合 CSV 导出。
- **影响范围**：文献数据迁移和后续分析。
- **复现方法**：URL/视图和模板审阅未找到 CSV。
- **文件/位置**：`app/papers/urls.py:8-9`；`app/papers/views.py`。
- **严重程度**：P1（验收规则明确指定）。
- **修复建议**：定义稳定 UTF-8 CSV schema、字段来源和权限范围，覆盖中文和大量数据。
- **是否阻止 V1**：**是**。

### P1-06 — 公开主页内容导出缺失

- **问题描述**：公开主页/公开快照没有用户可下载导出。
- **影响范围**：公开内容迁移和个人网站复用。
- **复现方法**：公开 URL 仅主页、论文、详情、附件和封面。
- **文件/位置**：`app/publications/urls.py:8-21`。
- **严重程度**：P1（验收规则明确指定）。
- **修复建议**：提供公开内容的稳定 JSON/Markdown/ZIP 或静态导出，严格只含已发布白名单字段。
- **是否阻止 V1**：**是**。

### P1-07 — 停用账号后无项目/对象所有权转移流程

- **问题描述**：停用会立即阻止登录且公开主页按 `public_enabled` 保持在线（文档已说明），但没有将项目、对象、快照转移给指定用户的受控操作。
- **影响范围**：成员离开、长期项目连续性、公开内容维护。
- **复现方法**：停用旧会话返回 302、登录失败、公开主页仍 200；审阅代码和运维文档未发现转移流程。
- **文件/位置**：`docs/admin-operations.md:12-16`；项目/对象 owner 外键及对应视图。
- **严重程度**：P1。
- **修复建议**：设计带审计、确认和范围预览的所有权转移命令/管理流程；不得通过开放 Admin 私自改 owner。
- **是否阻止 V1**：**是**；短期小团队可通过“不停用唯一所有者”规程缓解。

### P1-08 — 生产依赖未锁定

- **问题描述**：`pyproject.toml` 使用范围版本，构建时 `pip install .`；无锁文件、哈希或已解析约束，重建镜像会随时间变化。
- **影响范围**：可复现构建、安全修复审计、回滚一致性。
- **复现方法**：审阅依赖声明；验收镜像实际解析为 Django 5.2.16、bleach 6.4.0、Markdown 3.10.2、pypdf 6.14.2 等，但仓库不固定这些补丁版本。
- **文件/位置**：`pyproject.toml:11-18`；`Dockerfile:13`。
- **严重程度**：P1。
- **修复建议**：提交带哈希/锁定版本的生产依赖锁；建立定期更新和安全回归流程。
- **是否阻止 V1**：**是**。

### P1-09 — 登录后的页面执行无 SRI/CSP 的第三方 CDN JavaScript

- **问题描述**：HTMX 和 MathJax 从 unpkg/jsDelivr 加载；无 Subresource Integrity，也未设置 Content-Security-Policy。第三方不可用会破坏自动保存/公式，供应链被劫持可在认证页面执行脚本。
- **影响范围**：所有内部认证页面、科研内容隐私、离线/受限网络可用性。
- **复现方法**：模板与响应头静态审阅；未发现 `integrity` 或 CSP。
- **文件/位置**：`templates/base.html:13-14`；`Caddyfile`；Django production settings。
- **严重程度**：P1。
- **修复建议**：优先自托管固定版本静态资源；否则加入正确 SRI、严格 CSP、版本更新验证和无 CDN 降级策略。
- **是否阻止 V1**：**是**；对敏感内部科研数据也建议在试用前解决。

### P1-10 — 升级回滚没有可执行的不可变版本闭环

- **问题描述**：文档要求保留上一镜像，但默认镜像标签为 mutable `latest`，部署脚本重新构建当前标签；无自动旧标签、Git tag 或具体回滚命令。
- **影响范围**：失败升级、迁移回滚、恢复时间。
- **复现方法**：审阅 compose、deploy 和 upgrade 文档。
- **文件/位置**：`compose.yml:46`；`scripts/deploy.sh`；`docs/upgrade.md:20`；`docs/admin-operations.md:60`。
- **严重程度**：P1。
- **修复建议**：使用 commit/digest 不可变镜像；部署前记录当前 digest；提供应用回滚与数据库恢复的明确、演练过命令。
- **是否阻止 V1**：**是**。

### P1-11 — 恢复脚本对错误目标的保护不足

- **问题描述**：脚本要求 `BACKUP_DIRECTORY --yes` 并校验备份，但未要求输入/确认 Compose 项目、数据库名或环境指纹；一旦选中错误默认项目，会执行 `DROP SCHEMA public CASCADE`。
- **影响范围**：恢复操作的人为误选目标风险。
- **复现方法**：静态审阅脚本参数和破坏性 SQL；隔离演练确认校验通过后确实直接重建 schema。
- **文件/位置**：`scripts/restore.sh:4-5,48`。
- **严重程度**：P1。
- **修复建议**：要求显式目标项目/环境标识和二次匹配确认；显示 DB/卷/备份时间并拒绝默认值；生产恢复使用维护锁和预演模式。
- **是否阻止 V1**：**是**。

## 6. P2 和 P3 问题

以下各项均已记录，不在本轮修复。

### P2-01 — PRD 首页工作台未实现

- **问题/影响**：登录首页只重定向“我的内容”，缺少快速新建、最近、收藏、未整理、分享给我、参与项目、待回复评论、主页状态；影响日常研究入口。
- **复现/位置**：登录访问 `/`；`app/core/views.py:7-9`。
- **严重程度/建议/V1**：P2；实现仅含个人工作项的轻量 dashboard；不单独阻止 V1，但属于明显 PRD 缺口。

### P2-02 — Markdown 图片和编辑预览体验不完整

- **问题/影响**：清洗白名单没有 `img`，实测图片 Markdown 不产生 `<img>`；无实时/分栏预览、离页未保存提示和版本历史；公式标记保留但视觉渲染依赖外部 MathJax，未做真实浏览器跨端验收。
- **复现/位置**：渲染代码块/表格/图片/公式合成 Markdown；`app/research_objects/services.py:8-25`，编辑模板。
- **严重程度/建议/V1**：P2；安全支持受控图片源并增加预览/离页提示；不单独阻止 V1，冲突丢失已另列 P0。

### P2-03 — 删除与附件生命周期不清晰

- **问题/影响**：只有软删除，无恢复/彻底删除 UI；软删附件仍留盘但下载受阻；ResearchObject/用户级级联删除不会自动调用每个 FileField 的存储删除，可能产生孤立文件。
- **复现/位置**：`app/research_objects/models.py:125-127`，附件模型未覆盖 delete；软删自动化测试。
- **严重程度/建议/V1**：P2；明确保留期、恢复、硬删除和文件垃圾回收并审计；不单独阻止 V1。

### P2-04 — 搜索范围与分页不完整

- **问题/影响**：附件文件名和“我的公开快照”不进入搜索；无分页/相关性排序；归档内容默认出现且无说明。253 条合成对象时列表/搜索响应约 191/198 KB。
- **复现/位置**：`acceptance-marker.txt` 与公开快照标题搜索均 0；中文/标签/项目/评论通过；`app/research_objects/services.py:60-71`。
- **严重程度/建议/V1**：P2；增加权限安全的文件名/快照索引、明确归档规则、分页和稳定排序；不单独阻止 V1。

### P2-05 — 大列表未分页，项目列表存在 N+1

- **问题/影响**：对象、搜索、项目、共享和公开列表未分页；项目卡片逐项调用两个 count。31 个项目实测 66 次 SQL。
- **复现/位置**：项目列表查询计数；`templates/projects/list.html:13`，各列表视图。
- **严重程度/建议/V1**：P2；使用 annotate/prefetch 和统一分页；不单独阻止 V1。

### P2-06 — 上传类型校验与文件一致性仍有缺口

- **问题/影响**：HTML/SVG/Office/双扩展名可通过通用表单，伪 PDF 只凭 `.pdf` 可通过；高风险格式因所有下载强制 attachment+nosniff 而得到部分缓解。上传写存储与 DB 事务不是原子的，失败可能遗留文件；无附件删除端点。
- **复现/位置**：HTML/SVG/Office/`malware.exe.pdf` 为 valid；JS/EXE/超限被拒；`app/research_objects/forms.py:105-130`，`app/papers/forms.py:30-38`，下载 `views.py:311-314`。
- **严重程度/建议/V1**：P2；内容签名/允许列表、隔离存储、失败补偿和定期一致性扫描；不单独阻止 V1。

### P2-07 — 公开主页仅部分覆盖 PRD

- **问题/影响**：缺少独立公开项目实体/列表、软件与数据、CV 下载、自定义链接；影响完整学术主页。
- **复现/位置**：Profile/Snapshot 模型、表单、公开 URL 审阅。
- **严重程度/建议/V1**：P2；按白名单扩展公开内容类型；不单独阻止 V1。

### P2-08 — 快照更新与源对象删除语义需更明确

- **问题/影响**：编辑已发布快照后保存会立即更新公开页，缺少独立再次确认；源对象软删后快照继续在线，硬删被 PROTECT，用户界面没有解释。
- **复现/位置**：PublicationSnapshot 模型/表单/视图审阅。
- **严重程度/建议/V1**：P2；引入草稿修订→显式发布，并在删除界面提示快照结果；不单独阻止 V1。

### P2-09 — 安全审计和登录尝试保留范围不足

- **问题/影响**：审计覆盖分享、项目、评论删除、发布、备份恢复，但不记录登录成功/失败、密码/账号管理；LoginAttempt 仅在成功登录时删除匹配项，无全局保留清理。
- **复现/位置**：`app/audit/models.py:6-17`；`app/accounts/views.py:31-47`；`app/accounts/models.py:58-64`。
- **严重程度/建议/V1**：P2；增加最小安全事件与定期清理，避免记录敏感正文；不单独阻止 V1。

### P2-10 — 备份目标磁盘预检和 Windows 可移植性不足

- **问题/影响**：`check_storage` 检查媒体文件系统，但 backup 脚本未预估备份目标剩余空间。Windows Git Bash 首跑还会把容器路径改写，需 `MSYS_NO_PATHCONV=1`；目标 Linux 不受此问题影响。
- **复现/位置**：首轮备份因 `/app/var/media` 被改写失败且 `.partial` 正确清理；设置开关后通过；`scripts/backup.sh`。
- **严重程度/建议/V1**：P2；备份前检查目标空间并在文档注明受支持宿主/Windows 开关；不单独阻止 V1。

### P2-11 — 中文导出文件名退化

- **问题/影响**：中文标题 Markdown 导出头为 `259-research-object.md`，未保留中文或 RFC 5987 文件名。
- **复现/位置**：中文对象 HTTP 导出；`app/research_objects/views.py:249-257`。
- **严重程度/建议/V1**：P2；添加安全 ASCII fallback + `filename*` UTF-8；不单独阻止 V1。

### P2-12 — 列表过滤器未达到 PRD 范围

- **问题/影响**：我的内容仅支持类型、收藏、归档；缺少项目、标签、更新时间、状态、已发布、是否有附件。
- **复现/位置**：`app/research_objects/views.py:50-62`。
- **严重程度/建议/V1**：P2；增加后端查询参数和组合测试；不单独阻止 V1。

### P3-01 — 生产检查与 Caddy 格式警告

- **问题/影响**：强密钥下 `check --deploy` 仍提示 HSTS includeSubDomains/preload 未开启；单域渐进 HSTS 下这是可接受配置。Caddy 配置有效但提示未格式化。
- **复现/位置**：生产 check 与 `caddy validate`。
- **严重程度/建议/V1**：P3；上线确认域名策略后决定是否启用 HSTS 子域/preload，运行 `caddy fmt`；不阻止 V1。

## 7. 权限矩阵结果

`查看/评论/编辑/删除/分享管理/附件` 均由服务端实际请求或测试验证。`—` 表示该角色不适用该动作。

| 身份 | 私有对象查看 | 共享对象评论 | 编辑正文 | 改所有者 | 删除/收藏/归档 | 管理分享 | 下载附件 | 公开页 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 所有者 | PASS | PASS | PASS | 仅 owner 固定 | PASS | PASS | PASS | 仅显式发布 |
| 无权限用户 | 404 | 404 | 404 | 404 | 404 | 404 | 404 | 仅公开内容 |
| VIEWER | PASS | 404 | 404 | 404 | 404 | 404 | 仅 `include_attachments` | 仅公开内容 |
| COMMENTER | PASS | PASS | 404 | 404 | 404 | 404 | 仅 `include_attachments` | 仅公开内容 |
| EDITOR | PASS | PASS | PASS | 不可 | 404 | 404 | 仅单独授权 | 仅公开内容 |
| 项目 MEMBER | 仅显式项目共享 | PASS | 404 | 不可 | 404 | 404 | 仅项目附件开关 | 仅公开内容 |
| 项目 EDITOR | 仅显式项目共享 | PASS | PASS | 不可 | 404 | 404 | 仅项目附件开关 | 仅公开内容 |
| 已撤销用户 | 404（旧 URL 刷新也失效） | 404 | 404 | 404 | 404 | 404 | 404 | 仅公开内容 |
| 停用用户 | 无法登录；旧会话下一请求失效 | 无法使用 | 无法使用 | — | — | — | — | 若 profile 仍 `public_enabled`，公开主页继续 200（与文档一致） |
| 未登录用户 | 登录重定向/不可见 | 不可 | 不可 | 不可 | 不可 | 不可 | 仅明确公开附件 | 仅 profile enabled + snapshot published |
| Django 管理员 | 应用私有对象查询不自动放行 | 不自动 | 不自动 | 不自动 | 不自动 | 不自动 | 不自动 | 公开内容 | 

最后一行的对象级服务本身通过，但 Django Admin 的 Project 注册可改变项目所有者/成员并形成绕过路径，故整体管理员隐私边界为 FAIL（P0-03）。

## 8. 自动化测试结果

| 测试/检查命令 | 数量 | 通过 | 失败 | 跳过 | 时间/结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| `python manage.py test --verbosity 2`（无网络临时镜像，test settings） | 53 | 53 | 0 | 0 | 0.975 s；总命令约 3.5 s |
| Python `compileall`（临时容器） | — | PASS | 0 | — | 无输出、exit 0 |
| `makemigrations --check --dry-run` | — | PASS | 0 | — | `No changes detected` |
| `manage.py check`（恢复后 PostgreSQL） | — | PASS | 0 | — | `0 silenced` |
| `manage.py check --deploy`（强临时密钥） | — | PARTIAL | 0 | — | 2 个非阻断 HSTS 警告 |
| Shell 脚本语法（6 个 `.sh`） | 6 | 6 | 0 | 0 | exit 0 |
| `docker compose -f compose.yml config --quiet/--services` | 3 services | 3 | 0 | 0 | `db/web/caddy` |
| `caddy validate` | 1 | 1 | 0 | 0 | `Valid configuration`；有 fmt 警告 |
| 生产镜像构建 | 1 | 1 | 0 | 0 | 缓存构建成功；61,471,324 bytes |
| migrations 重跑 | 30 记录 | PASS | 0 | 0 | `No migrations to apply` |
| `init_admin` 两次 | 2 | 2 | 0 | 0 | 首次 `Created`，第二次 `Updated` |

自动化测试按模块：sharing 14、research_objects 13、publications 10、papers 5、accounts 3、core operations 4、init_admin 1、health 3。

## 9. 数据安全结果

| 项目 | 状态 | 实际结果 |
| --- | --- | --- |
| Git 敏感数据 | PASS | `.env`、DB/dump、media、backups、PDF、日志、密钥、证书、Token 均未被跟踪；只跟踪 `.env.example` |
| 备份 | PASS | PostgreSQL SQL gzip + media tar gzip + manifest + SHA256；原子 `.partial`；7 日/4 周保留逻辑；首次合成备份 DB 8,671 bytes、media 244 bytes（压缩后） |
| 篡改检测 | PASS | 向 DB gzip 副本追加 1 byte 后恢复 exit 1；校验在停止服务前失败，在线合成标记保持不变 |
| 同栈恢复 | PASS | 备份后修改 DB、增加记录、删除媒体；恢复后旧正文、媒体内容和 SHA-256 恢复，备份后记录消失 |
| 全新栈恢复 | PASS | 恢复脚本生成的新 Compose 项目：30 迁移、4 用户、Django/storage check 通过并自动清理 |
| 全新栈功能恢复 | PASS | 另一个全新项目实际登录成功；私有对象 200、共享 EDITOR 200、撤销用户 404、附件 200、搜索 200、公开主页/详情 200；随后 `down -v` |
| 单项导出 | PASS | Markdown 内容逐字一致；BibTeX 200；权限由 visible queryset 约束 |
| 批量导出 | FAIL | ZIP、论文 CSV、公开主页导出缺失（P1-04/05/06） |
| 附件授权 | PASS | 分享正文不自动分享附件；单独授权；撤销即时；Caddy 不公开 media；随机存储名；下载 attachment+nosniff |
| 附件格式/一致性 | PARTIAL | 高危脚本/EXE/超限拒绝；HTML/SVG/Office/双扩展/伪 PDF 仍可进入私有存储；文件生命周期缺口见 P2-06 |
| 配额 | FAIL | 用户配额不存在（P1-01） |
| 数据库/磁盘一致性 | PARTIAL | 恢复一致性通过；级联删除和失败写入可能产生孤立文件 |
| 异机备份 | NOT TESTED | 仅文档要求；未连接任何真实外部存储 |

恢复注意：`BACKUP_CREATED` 事件是在备份完成后写入，因此恢复“该备份自身”不会包含该事件；恢复完成后 `RESTORE_COMPLETED` 事件存在。这是时间顺序结果，不是恢复丢记录。

## 10. 资源占用

全部数据来自隔离 Docker；没有执行破坏性压力测试。

| 指标 | 实测/配置 |
| --- | --- |
| Web 空闲 | 119.6 MiB / 768 MiB，3 PIDs |
| PostgreSQL 空闲 | 24.67 MiB / 512 MiB，8 PIDs |
| Caddy 空闲 | 9.824 MiB / 128 MiB，7 PIDs（无端口映射、实际 Caddyfile） |
| 三服务观测空闲合计 | 约 154 MiB |
| 配置内存上限合计 | 1,408 MiB；为 2 GB 主机保留约 640 MiB 给宿主、Docker、页缓存和峰值 |
| Gunicorn | 2 workers；30 s timeout；1000±100 请求回收 |
| PostgreSQL | 30 connections、128 MB shared_buffers、4 MB work_mem、32 MB maintenance_work_mem |
| 253 对象/120 页面请求 | 状态全部 200；Web 最高采样 133 MiB，DB 28.39 MiB |
| 31 项目列表 | 66 SQL、14.6 KB、116.9 ms；确认 N+1 |
| 253 对象列表/搜索 | 各 5 SQL；约 190.8/197.6 KB；80.0/60.1 ms |
| 15 MB 合成 PDF 服务导入 | 成功；采样 CPU 峰值约 15.54%；精确瞬时 RSS 峰值未被低频采样捕获 |
| 40 MB 合成 PDF 真实 Gunicorn HTTP 导入 | 41,943,515 bytes；302 到新对象；采样 Web 最高 119.9 MiB、CPU 17.22%，DB 约 28.98 MiB |
| 约 73 MB 合成媒体备份 | 3.9 s；Web 最高采样 136 MiB、CPU 15.11%，DB 约 28.43 MiB |
| 应用镜像 | 61,471,324 bytes |
| PostgreSQL/Caddy 镜像 | 117,165,949 / 23,925,148 bytes |
| 三镜像合计 | 202,562,421 bytes（约 193.2 MiB） |
| 初始恢复媒体 | 30 bytes 合成内容；加载 PDF 后临时媒体卷 73,414,066 bytes |
| 临时 PostgreSQL 数据目录 | 67,678,985 bytes |
| static 卷 | 1,512,388 bytes |
| 存储预检 | `status=ok`；默认最低剩余空间 1 GiB |
| 启动耗时 | 隔离 PostgreSQL + Web 绕过 P0 后约 12 s 达到 healthy；完整新栈恢复演练约 12–15 s |
| ZIP 导出峰值 | NOT TESTED：功能不存在 |
| 真实 2–10 人并发和长期泄漏 | NOT TESTED：本轮仅轻量合成循环，无破坏性压力 |

资源结论：当前服务基线符合 2 GB 目标，但配额缺失、无分页/N+1、PDF 全量 `upload.read()` 和 ZIP 缺失意味着不能据此宣称长期 2–10 用户容量已经通过。部署文档建议 1–2 GB swap，合理但必须在真实服务器验证。

## 11. 真实服务器待验证项

以下均为 `NOT TESTED`，不得视为通过：

1. 真实域名与 DNS 解析。
2. 公网 80/443、Caddy 首次证书签发和自动续期。
3. SSH 密钥、来源地址限制及管理员主机加固。
4. UFW/云防火墙实际规则。
5. 从外部机器确认 PostgreSQL 5432 不可达。
6. Docker 随主机自动启动。
7. 真实主机重启后的 DB/Web/Caddy 恢复。
8. cron/systemd 定时备份与健康检查。
9. 加密异机备份、传输、保留和恢复。
10. Docker 日志轮换在长期运行中的实际生效。
11. 磁盘告警的监控系统与通知链路。
12. 1–2 GB swap 配置和压力下换页行为。
13. 邮件/通知（当前无真实配置）。
14. 真实用户试用、移动端浏览器和可访问性。
15. 真实网络延迟、Crossref 可用性/限流和证书链。
16. 真实 PDF/附件长期增长及备份窗口。
17. 生产升级、失败迁移和应用/数据库回滚演练。
18. 真实浏览器中的 MathJax、图片、代码块、移动端视觉结果。

## 12. V1 发布阻断清单

### 同时阻断内部试用与正式 V1

1. P0-01：HTTPS=true 时生产健康检查失败，三服务栈无法按文档启动。
2. P0-02：并发编辑静默覆盖正文，存在数据丢失。
3. P0-03：Django Admin 暴露私人项目并可形成成员/所有者权限绕过。

### 阻断正式 V1；修复 P0 后可基于明确限制评估内部试用

4. P1-01：用户配额缺失。
5. P1-02：arXiv、来源/置信度、用户元数据修正缺失。
6. P1-03：异常长 PDF 标题导致导入失败。
7. P1-04：个人全部内容 ZIP 缺失。
8. P1-05：论文 CSV 缺失。
9. P1-06：公开主页导出缺失。
10. P1-07：停用账号无所有权转移。
11. P1-08：生产依赖未锁定。
12. P1-09：认证页面依赖无 SRI/CSP 的第三方 JavaScript。
13. P1-10：没有不可变镜像和可执行回滚闭环。
14. P1-11：恢复脚本目标环境保护不足。

## 13. 内部试用前最低修改清单

按优先级和粗粒度时间带估算；不是精确工时。

| 优先级 | 最低修改 | 时间带 |
| --- | --- | --- |
| 1 | 修复生产健康检查与 HTTPS=true 启动链路，并添加 Compose 回归 | 小于 1 小时 |
| 2 | 从 Django Admin 移除私人 Project/Member 或做严格不可读/不可改限制，并补权限测试 | 1–4 小时 |
| 3 | 增加服务端乐观锁、409 冲突处理、自动保存冲突 UI 和双标签页测试 | 半天–1 天 |
| 4 | 自托管 HTMX/MathJax，增加最小 CSP，避免认证页第三方执行 | 1–4 小时 |
| 5 | PDF 外部 metadata 长度/字符清洗与可靠降级 | 1–4 小时 |
| 6 | 为试用提供至少默认用户配额、原子计量和管理员调整 | 半天–1 天 |
| 7 | 给恢复脚本增加目标项目/数据库指纹、dry-run 和二次确认 | 1–4 小时 |
| 8 | 固定依赖和镜像 digest，写出可执行回滚步骤 | 半天 |

只有第 1–3 项全部完成并回归通过后，才建议重新评估内部试用；若试用数据敏感，第 4 项也应视为前置条件。P1 导出、arXiv 和所有权转移可在受限内部 Beta 中排期，但必须向试用者明确不可用范围，并禁止把该版本称为 V1。

## 14. 建议的版本状态

**V0.9 Release Candidate — Blocked**

不建议使用 `V1.0 Ready`、`V1` 或“可生产部署”。修复 P0 并完成最低回归后，可考虑 `V0.9.1 Internal Beta`；所有 P1 关闭且真实服务器清单完成后，再做一次正式 V1 验收。

## 15. 验收证据

### Git 与文件

- 工作目录：`D:\research_workspace`
- Git top-level：`D:/research_workspace`
- 分支：`main`
- commit：`e38c09dfa67e84462601215d8396262f4300a98a`
- 报告生成前：`git status --porcelain=v1 --untracked-files=all` 为空；`git diff --stat` 为空。
- `git remote -v`：空。
- 最近历史：Stage 0 至 Stage 5 共 7 个清晰 commit。
- 迁移：19 个已跟踪迁移目录文件，包含 12 个业务迁移版本；漂移检查为零。
- 敏感跟踪扫描：未发现 `.env`、数据库、dump、media、backups、PDF、日志、私钥、证书或 Token。

### 关键命令与输出摘要

| 命令/动作 | 输出摘要 |
| --- | --- |
| `docker build --pull=false -t research-workspace-lite:acceptance-e38c09d .` | 成功；61,471,324 bytes；按“不删除镜像”要求保留 |
| 无网络容器 `manage.py test --verbosity 2` | Found 53；Ran 53 in 0.975s；OK；0 skipped |
| `compileall` | exit 0 |
| `makemigrations --check --dry-run` | `No changes detected` |
| `manage.py migrate --noinput`（重复） | `No migrations to apply` |
| `init_admin` 两次 | `Created administrator`；`Updated administrator` |
| `manage.py check --deploy` | 强密钥下仅 W005/W021 两个 HSTS 可选警告 |
| `docker compose -f compose.yml config --services` | db / web / caddy |
| `caddy validate` | Valid configuration；fmt warning |
| HTTPS=true 生产 Web | health log 反复 TLS handshake timeout；关闭重定向后 healthy |
| 权限合成矩阵 | VIEWER/COMMENTER/EDITOR、项目 MEMBER/EDITOR、撤销、附件、管理员对象 bypass 均按预期；Admin Project 页面另行 FAIL |
| 两标签页保存 | `final_content=tab two stale text`；`tab_one_lost=True`；无冲突检测 |
| PDF 异常 metadata | 300 字符有效 PDF title → `DataError`；对象/附件记录均未新增 |
| 40 MB HTTP PDF | 41,943,515 bytes；302 到 `/workspace/256/` |
| 搜索补测 | 中文/正文/标签/项目/评论通过；文件名和公开快照为 0；特殊字符不报错；删除排除；归档出现 |
| 上传矩阵 | HTML/SVG/Office/双扩展/伪 PDF 接受；JS/EXE/超限拒绝；下载 attachment+nosniff |
| 备份 | gzip + SHA256 + manifest 成功；首轮 DB 8,671 bytes、媒体 244 bytes |
| 破坏备份副本 | `database.sql.gz: FAILED`，restore exit 1，在线标记仍存在 |
| 恢复演练 | 30 migrations、4 users；DB/媒体/hash 恢复；新栈功能断言全部通过 |
| 清理 | `rwlaccept*` 容器/卷/网络均无残留；本机临时备份/破坏副本/恢复报告已删除；镜像按限制保留 |

### 涉及的主要文件

- `research_workspace_prd_v1.md`、`README.md`、`IMPLEMENTATION_PLAN.md`
- `docs/deployment.md`、`docs/backup-restore.md`、`docs/upgrade.md`、`docs/admin-operations.md`、`docs/recovery-verification.md`
- `compose.yml`、`compose.override.yml`、`Caddyfile`、`Dockerfile`、`.env.example`、`pyproject.toml`
- `scripts/backup.sh`、`scripts/restore.sh`、`scripts/recovery-drill.sh`、`scripts/deploy.sh`、`scripts/healthcheck.sh`
- `config/settings/*`
- `app/**/models.py`、`forms.py`、`services.py`、`views.py`、`urls.py`、`admin.py`、`tests/*`、`migrations/*`
- `templates/**`、`static/**`

### 测试数据说明

- 自动化测试使用内存 SQLite。
- 手工验收使用唯一命名的临时 Compose 项目、临时 PostgreSQL/媒体卷和 `.invalid` 邮箱域的合成账号。
- 合成数据包括 4 个角色账号、3 个基础对象、1 个项目、评论、私有附件、公开快照，以及资源测试生成的对象/PDF。
- 未读取、复制、修改或删除现有开发/真实用户数据库、附件、工作区 `backups/` 或任何真实生产资源。
- 本轮未执行 `git add`、`git commit`、`git push`、`git reset`、`git clean` 或任何 prune。

