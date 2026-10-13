# Sofia 照片多要素搜索器

<!-- en-intro -->
**Sofia Photo Search** — face-first multi-factor search for local photo libraries: filter by face, full view, focus, text, GPS and date. Built on FastAPI + MySQL + FAISS, with scanning and index-maintenance tooling.
<!-- /en-intro -->

---

> 本项目已进入可落地运行阶段。本文档用于“一次看懂 + 快速接手 + 稳定运维”。

## 1. 项目定位

Sofia 是一个面向本地/局域网照片库的多要素检索系统，核心目标是：

- 以**人脸**为主线检索目标照片
- 叠加**全景/聚焦/文字/GPS/日期**等条件进行精筛
- 提供可持续运维能力（扫描、断点续扫、时间修复、索引体检与压实、健康检查）

当前实现形态：

- 后端：FastAPI + MySQL + FAISS
- 前端：原生 HTML/CSS/JS（无外部 UI 框架）
- 部署：Windows 本地运行（也可局域网访问）

---

## 2. 已落地核心能力

### 2.1 检索能力

- 人脸检索
  - 多标准图
  - 人脸逻辑 OR / AND
  - 至少匹配脸数（自动或手动）
  - 预裁剪开关（提升精度或提升召回）
- 全景检索（整图语义）
- 聚焦检索（中心 / 垂直 / 十字 / 横向）
- 文字检索
  - 文件名/目录关键词
  - AND / OR
  - “全类型文件”模式
- GPS 检索
  - 先在结果中设置 GPS 中心，再按半径查询
  - 支持“GPS + 要素”叠加查询
- 日期检索（起止日期 + 快捷区间）

### 2.2 结果浏览与排序

- 分批浏览（每批 55 张）
- 翻页：首批 / 上批 / 下批 / 末批
- 排序：
  - 时间新->旧 / 旧->新
  - 相似度高->低 / 低->高
  - 脸数多->少 / 少->多
  - 限定脸数（0..n，n 为当前结果最大脸数）
  - 距参考点近->远 / 远->近
  - 文件名 A->Z / Z->A

### 2.3 结果操作

- 设为标准照片
- 设为 GPS 中心
- 原图查看
- 重命名（物理文件 + 数据库同步）
- 删除（移动到回收目录 + 数据库清理）
- 批量下载（支持后台打包 zip）

### 2.4 运维与安全操作

- 扫描控制：增量/全量/断点续扫 + 暂停/继续/停止
- EXIF 时间修复（可选目录，支持进度 x/n）
- 索引健康检查（face + vision）
- 索引体检/压实（dry-run 与正式执行分离，带确认短语）
- 登录认证（多密码 + 目录 ACL）
- 用户权限设置（管理员二次验证后可表单化维护 `auth_policies.json`）

---

## 3. 技术架构

- Web/API：FastAPI（`service/app.py`）
- 数据库：MySQL（`db/schema.sql`）
- 人脸引擎：InsightFace（默认 `antelopev2`）
- 视觉引擎：OpenCLIP（默认 `ViT-B-32/openai`）
- 向量索引：FAISS
  - 人脸索引：`faiss.index`
  - 全景/聚焦索引：`vision.index`
- 索引安全机制：`*.prev` 回滚 + `*.manifest.json` 健康校验 + 原子替换

---

## 4. 目录结构（核心）

```text
照片搜索/
├─ service/                 # 后端代码
│  ├─ api/v1/endpoints/     # 各类 API
│  ├─ db/mysql.py           # SQL 与数据访问
│  ├─ scan/                 # 扫描与时间修复
│  ├─ index/manager.py      # FAISS 索引读写/压实/健康
│  └─ app.py                # FastAPI 入口
├─ ui/                      # 前端页面与脚本
├─ db/                      # 建库/升级 SQL
├─ logs/                    # 运行日志（photo_search.log）
├─ pre_deleted/             # 删除回收目录
├─ archive/                 # 历史备份
├─ db2.ini                  # 运行配置
├─ requirements.txt
├─ requirements-ml.txt
└─ *.bat                    # 启动与扫描脚本
```

---

## 5. 环境要求

- Windows 10/11
- Python 3.13（项目当前实测）
- MySQL 8.x（或兼容）
- GPU（推荐）：RTX 40 系列可显著提升速度

安装依赖：

```bash
pip install -r requirements.txt
pip install -r requirements-ml.txt
```

---

## 6. 数据库初始化

1. 创建数据库（参考 `db/create_db.sql`）
2. 导入表结构：`db/schema.sql`
3. 如是旧库升级，按需执行 `db/upgrade_*.sql`
4. 本轮多密码目录 ACL 升级对应：`db/upgrade_auth_policy_scope.sql`

---

## 7. 配置文件（db2.ini）

关键配置：

- `[database]`：MySQL 连接
- `[paths]`：
  - `photo_roots`（可多个，用 `;` 分隔）
  - `index_dir` / `thumb_dir` / `export_dir`
- `[face]`：人脸模型
- `[vision]`：视觉模型
- `[scan]`：扫描节奏
- `[auth]`：会话签名与策略文件位置

`db2.ini` 只保留认证运行参数；真正的“密码 -> 可访问目录”映射放在 `config/auth_policies.json`，由服务器管理员维护，可用明码，默认拒绝未授权目录。

### 7.1 在线权限配置

系统设置中已提供“用户权限设置”入口，特点如下：

- 仅管理员可见
- 进入配置界面前，必须再次输入当前管理员密码完成二次验证
- 以表单方式读取和编辑 `config/auth_policies.json`
- 支持新增 / 删除 / 修改策略的全部核心字段：
  - `version`
  - `updated_at`
  - `default_deny`
  - `policies[].id / name / enabled / is_admin / password / roots / note`
- 保存前自动备份原文件到：`archive/auth_policy_backups/`
- 保存成功后立即清理服务端策略缓存，新配置对后续请求即时生效

建议：

- 修改前仍建议额外手工备份一次关键配置
- 至少保留一个启用中的管理员策略，避免把自己锁死
- `updated_at` 可留空，保存时会自动写入当前时间

`db2.ini` 不入库（含密码），首次部署按下面的伪代码配置新建。尖括号 `<...>` 为必须替换项，其余为默认值，可按需调整。

注意：注释必须单独成行。写在值后面的 `# 注释` 会被当成值的一部分。

```ini
; ===== MySQL 连接 =====
[database]
host = 127.0.0.1
port = 3306
user = <db_user>
password = <db_password>
; 生产库名；v2 隔离版必须换成别的库名，如 photo_search_v2
database = photo_search
charset = utf8mb4

; ===== 目录 =====
[paths]
; 照片根目录，多个用 ; 分隔
photo_roots = D:\photos;D:\archive
; 索引 / 缩略图 / 导出目录，缺省为项目下 data\index、data\thumbs、data\export
index_dir = <cache_dir>\index
thumb_dir = <cache_dir>\thumbs
export_dir = <cache_dir>\export
; true 时禁止改动源照片（重命名、删除）；v2 隔离版必须为 true
source_read_only = false

; ===== 人脸模型 =====
[face]
engine = insightface
; 无 NVIDIA 显卡时设为 false
use_gpu = true
model_name = antelopev2
embedding_dim = 512

; ===== 视觉 / 文字搜图模型 =====
[vision]
enabled = true
model_name = ViT-B-32
pretrained = openai
embedding_dim = 512
; 可选：中文文本编码模型目录，留空则不启用
text_model =

; ===== FAISS 索引 =====
[index]
backend = faiss
; hnsw / ivfpq 等
index_type = hnsw
nlist = 4096
pq_m = 64
hnsw_m = 32

; ===== 扫描节奏 =====
[scan]
; true 时仅在电脑空闲 idle_minutes 分钟后扫描
scan_idle_only = false
idle_minutes = 10
cpu_limit = 40
gpu_limit = 30
io_limit = 120
scan_batch_size = 100

; ===== 认证 =====
[auth]
; 旧版单密码兼容回退，正式多用户权限见 auth_policies.json
password = <legacy_password>
; 会话签名密钥，用随机长字符串，如 python -c "import secrets;print(secrets.token_hex(32))"
session_secret = <random_secret>
policies_json = config/auth_policies.json
; 可选，缺省 photo_search_auth
cookie_name = photo_search_auth

; ===== 服务端口（可选）=====
[server]
; 缺省 5090；环境变量 PHOTO_SEARCH_PORT 优先
port = 5090
```

v2 隔离版读取 `db2_v2.ini`（可参考仓库中的 `db2_v2.ini.example`），启动时会强制检查以下几条：

- `database` 不能是 `photo_search`
- `photo_roots` 不能为空
- `index_dir` / `thumb_dir` / `export_dir` 不能与 `db2.ini` 相同
- `source_read_only = true`
- 默认端口为 5091，cookie 名为 `photo_search_v2_auth`

支持环境变量：

- `PHOTO_SEARCH_CONFIG`：指定配置文件路径
- `PHOTO_SEARCH_PORT`：覆盖默认端口（默认 5090）

`config/auth_policies.json` 示例：

```json
{
  "version": 2,
  "default_deny": true,
  "policies": [
    {
      "id": "admin",
      "name": "管理员",
      "enabled": true,
      "is_admin": true,
      "password": "<ADMIN_PASSWORD>",
      "roots": ["D:/photos", "D:/photo"]
    },
    {
      "id": "user2",
      "name": "用户2",
      "enabled": true,
      "is_admin": false,
      "password": "<USER2_PASSWORD>",
      "roots": ["D:/photos/school/z"]
    }
  ]
}
```

权限规则：

- 每个密码对应一个 `policy_id`
- 非管理员策略只能访问 `roots` 内照片
- 搜索结果、缩略图、原图、下载、重命名、删除、标准照片、收藏夹、搜索会话都按 `policy_id` 隔离
- 旧版 `db2.ini [auth].password` 仅作为兼容回退，不再作为正式多用户权限配置

---

## 8. 启动方式

### 8.1 推荐（脚本）

- `智能启动(优先续扫否则增量).bat`（日常首选）
- `启动并断点续扫(重启+续扫).bat`
- `启动并扫描(重启+增量).bat`
- `启动照片搜索(仅启动).bat`

### 8.2 命令行

```bash
python -m uvicorn service.app:app --host 0.0.0.0 --port 5090
```

访问：

- 本机：`http://127.0.0.1:5090`
- 局域网：`http://<你的IP>:5090`

---

## 9. 日常操作流程（推荐）

1. 登录系统
2. 上传标准照片（可多张）
3. 勾选要素（人脸/全景/聚焦/文字）并设置细项
4. 点击“开始搜索”
5. 用“首批/上批/下批/末批”浏览
6. 用排序与“限定脸数”快速收敛结果
7. 对命中结果执行：标准照片 / GPS中心 / 重命名 / 删除 / 下载

---

## 10. 扫描、时间修复、压实（运维重点）

### 10.1 扫描

- 增量扫描：日常主力
- 全量扫描：仅重建或大改后使用（耗时长）
- 断点扫描：异常中断后恢复

> 提示：大量“新增/移动/删除”后，至少跑完一次增量扫描，才能完成数据库与索引同步。

### 10.2 时间修复（EXIF）

支持在 `photo_roots` 下选择任意子目录执行，规则为：

1. 优先读取 EXIF 时间
2. 无 EXIF 时，按路径中的“年/月”推断
3. 仍无法推断时，回退文件 mtime

修复进度提供 `processed/total`（x/n）显示。

### 10.3 索引体检与压实

入口：系统设置 -> 索引冗余压实

- 体检（dry-run）：不改写索引，先评估
- 压实人脸 / 压实视觉 / 一键全压实
- 正式压实需输入确认短语：`我已备份并确认压实`

执行前建议：

- 确保扫描已停止
- 已完成数据库与索引备份

---

## 11. 删除与重命名策略

### 11.1 删除（结果中的“删除”）

不是直接物理抹除，而是：

1. 文件移动到：`<项目目录>\pre_deleted\...`
2. 写入删除清单：`pre_deleted\_manifest.jsonl`
3. 数据库将对应照片标记/清理关联（faces、photo_embeddings、standard_photo 等）

### 11.2 重命名

- 修改物理文件名
- 同步更新数据库路径与文件名
- 若数据库更新失败，会回滚文件改名
- 扫描进行中禁止重命名

---

## 12. API 速查

认证：

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/status`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/admin/reverify`
- `GET /api/v1/auth/admin/policies`
- `PUT /api/v1/auth/admin/policies`

搜索：

- `POST /api/v1/search/multi`
- `POST /api/v1/search/face`
- `GET /api/v1/search/batch`
- `GET /api/v1/search/gps`
- `POST /api/v1/search/gps_multi`
- `POST /api/v1/search/person`

扫描与修复：

- `POST /api/v1/scan`
- `POST /api/v1/scan?full=true`
- `POST /api/v1/scan?resume=true`
- `POST /api/v1/scan/pause`
- `POST /api/v1/scan/resume`
- `POST /api/v1/scan/stop`
- `GET /api/v1/scan/progress`
- `POST /api/v1/scan/exif_repair`
- `GET /api/v1/scan/exif_repair_status`
- `GET /api/v1/scan/exif_repair_dirs`
- `GET /api/v1/scan/exif_repair_browse`

状态与压实：

- `GET /api/v1/status`
- `GET /api/v1/vision/status`
- `GET /api/v1/face/status`
- `GET /api/v1/index/compact/status`
- `POST /api/v1/index/compact/start`

照片与下载：

- `POST /api/v1/photos/{photo_id}/rename`
- `POST /api/v1/photos/trash`
- `POST /api/v1/photos/download_zip_prepare`
- `GET /api/v1/photos/download_zip_status`
- `GET /api/v1/photos/download_zip_file`

---

## 13. 日志与排错

日志位置：

- `logs/photo_search.log`

常见检查：

1. 服务启动失败：先看数据库连接和 `db2.ini`
2. 搜不到新文件：确认增量扫描是否跑完
3. 索引警告 `manifest stale`：重启服务后复查，必要时体检/压实
4. 时间异常：使用“时间修复”并选择目标目录

---

## 14. 安全建议（上线前必做）

- 修改 `db2.ini` 中数据库密码与 `session_secret`
- 生产环境不要把真实 `auth_policies.json` 提交到代码仓库
- 限制 `config/auth_policies.json` 与 `archive/auth_policy_backups/` 的文件访问权限
- 局域网部署时建议仅开放可信网段

---

## 15. 维护约定

- 重要改动前先做备份，统一存放到 `archive/`
- 扫描期间避免重命名/压实等重操作
- 大规模目录变更后：增量扫描 -> 状态核对 -> 按需体检/压实

---

## 16. 项目状态

- 当前状态：**可落地运行**
- 适合场景：学校安保、档案图片管理、家庭/单位照片库检索
- 当前已落地：多密码目录 ACL、按 `policy_id` 隔离的标准照片/收藏夹/搜索会话
- 后续可扩展：审计日志、权限分级、集群化索引

---

## 17. 近期更新（手机前端）

### 17.1 搜索结果开关优化

- 手机端将“搜索结果”开关改为底部工具条内的图标按钮（📰）+ 文本按钮
- 文本按钮（“展开结果/收起结果”）与图标按钮行为一致，均可点击切换
- 手机端隐藏原“搜索结果”标题行，避免重复入口
- 收起搜索结果时，整张结果卡片同步隐藏，移除残留空白行

### 17.2 搜索引导提示

- 在“开始搜索”按钮下方新增简短提示卡片
- 内容聚焦两种路径：快速浏览全部、上传标准照后精准检索

### 17.3 手机底部交互整理

- 手机端将排序下拉、限定脸数、结果开关、批次按钮整合为单一底部工具条
- 工具条上排放“排序 + 限定脸数 + 结果开关”，下排放“首批/上批/下批/末批”
- “开始搜索”下方顶部批次按钮在手机端隐藏，PC端保持不变

### 17.4 浏览器模式稳定性修复

- 修复“手机浏览器地址栏显示时” header/footer 漂移问题
- `navbar` 改为稳定贴顶，不再跟随 `visualViewport.offsetTop` 上下漂移
- 保留 `visualViewport` 底部补偿，用于 footer、底部工具条、回顶/回底按钮定位稳定
- 软键盘弹起时不将 footer 顶到键盘上方，保持底部锚定策略

### 17.5 窄屏浏览器与手机端统一

- PC 浏览器缩窄到手机断点（<=768px）后，统一沿用手机端交互与布局
- 搜索结果区域自动切换为手机端紧凑模式，使用图标化/底部工具条入口
- 窄屏场景下不再额外维护“桌面窄窗专用布局”，以减少分支和错位风险

---

## 18. 许可证

本项目按 MIT License 发布，版权所有 (c) 2026 Lu Xudong。

- `LICENSE`：英文原件，以此版本为准。
- `LICENSE-ZH.md`：中文对照，仅供阅读参考；发生歧义时以英文原件为准。

---

## 19. 关于本公开仓库

本仓库是从私有运行环境整理出的公开版本，整理时做了以下处理：

- 示例配置中的真实目录、家属姓名、个人邮箱与家庭服务器地址，已替换为中性占位符。
- 移除了商业计划、内部评审记录、实施交接文档，以及含真实照片路径的界面截图。
- GPS 参考点常量统一改名为 `REFERENCE_GPS`，坐标置为 `{ lat: 0, lon: 0 }`，界面文案相应改为「距参考点」。部署时请填入自己的坐标。
- 时间修复相关路由统一改名为 `exif_repair`，前端调用与本文档已同步更新。

部署前请按第 14 节的安全建议，自行设置数据库密码、`session_secret` 与策略文件，不要沿用示例里的 `CHANGE_ME`。
