# 征信报告自动化审核系统 — 设计文档

**日期：** 2026-03-27
**阶段：** 第一期（核心解析 + 持久化 + OCR 支持）
**作者：** 信贷风控专家

---

## 一、需求背景

信贷风控专家在工作中需要对客户提供的人民银行信用报告进行审核。为提高审核效率并推动风控系统数字化升级，需开发一套自动化信用报告审核程序。

**第一期目标：**
1. 支持多种文件类型（原生PDF、扫描PDF、图片）的报告解析
2. 提取字段后持久化存储到数据库
3. Web 版（部署 VPS）和本地版（exe）双端支持
4. 小团队（2-10人）多用户使用，数据按用户隔离

**后续期（暂不实现）：**
- 字段计算与规则审核引擎
- 可视化展示
- LLM 风险分析与审核建议

---

## 二、技术选型

| 模块 | 技术 | 说明 |
|------|------|------|
| 后端 API | FastAPI + uvicorn | REST API，支持异步 |
| 前端 UI | Streamlit | Web/本地共用同一套代码 |
| 数据库（Web版）| PostgreSQL | 多用户并发，VPS 部署 |
| 数据库（本地版）| SQLite | 零配置，本地单机 |
| PDF 解析 | pdfplumber + PyPDF2 | 原生 PDF 文字/表格提取，防篡改校验 |
| OCR | GLM-OCR（本地部署） | 扫描件/图片识别，效果不佳时扩展为云端API |
| 认证 | JWT | 用户登录鉴权 |
| 打包（本地版）| PyInstaller | 打包为 exe，内嵌服务 |
| 容器化（Web版）| Docker + docker-compose | 一键部署所有服务 |

---

## 三、整体架构

```
┌─────────────────────────────────────────────────────┐
│                    前端层                             │
│   Streamlit Web App (web版 / 本地exe版共用同一代码)    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP REST API
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI 后端                         │
│  ┌────────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ 文件处理层  │ │ 解析引擎  │ │    用户/认证模块    │  │
│  │ (上传/路由) │ │(企业/个人)│ │  (JWT, 2-10人)    │  │
│  └────────────┘ └──────────┘ └────────────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │              OCR 处理模块（按需触发）             │  │
│  │         GLM-OCR（本地部署）                     │  │
│  └────────────────────────────────────────────────┘  │
└──────────┬────────────────────────┬──────────────────┘
           │                        │
┌──────────▼──────────┐  ┌──────────▼──────────────────┐
│   PostgreSQL 数据库  │  │      文件存储                │
│  (报告数据/用户/历史) │  │  (上传的原始PDF/图片文件)    │
└─────────────────────┘  └─────────────────────────────┘
```

---

## 四、文件处理策略

```
上传文件
    │
    ├── 原生 PDF（有文字层）  → pdfplumber 直接提取文字+表格
    ├── 扫描版 PDF（无文字层）→ 转图片 → GLM-OCR → 提取文字
    └── 图片文件（jpg/png）  → GLM-OCR → 提取文字
```

检测原生/扫描 PDF 的方式：尝试 pdfplumber 提取文字，若文字量低于阈值则判定为扫描件，转入 OCR 流程。

---

## 五、解析引擎设计

复用旧代码三个 Parser 类的核心逻辑，重构为统一接口：

```
ReportParserFactory          # 工厂类，自动识别报告类型并分发
    └── BaseParser            # 抽象基类，统一输出格式 ReportResult
         ├── EnterpriseParser       # 企业征信自查版（对应旧 CR_CIParser）
         ├── PersonalDetailParser   # 个人征信详版（对应旧 CR_PDParser）
         └── PersonalSimpleParser   # 个人征信简版（对应旧 CR_PSParser）

OCRPreprocessor              # OCR 预处理，仅扫描件/图片触发
ReportValidator              # 防篡改校验（复用旧代码）
```

**解析流程：**
```
上传文件 → 文件类型检测 → [OCR预处理] → ReportParserFactory
→ Parser.parse() → ReportValidator → 写入数据库 → 返回 report_id
```

---

## 六、数据库设计

### 表结构

**users（用户表）**
```
id, username, password_hash, role(admin/user), created_at
```

**reports（报告主表）**
```
id, user_id(FK), report_type, file_path, file_type,
report_number, subject_name, report_date,
is_valid, parse_status, created_at
```

**enterprise_reports（企业报告数据）**
```
id, report_id(FK), credit_code, company_name,
registered_capital, ... (企业基本信息字段)
```

**personal_reports（个人报告数据）**
```
id, report_id(FK), id_number, name, age,
marital_status, ... (个人基本信息字段)
```

**credit_accounts（信贷明细，一报告多条）**
```
id, report_id(FK), account_type, institution,
amount, balance, status, data_json
```

**query_records（查询记录）**
```
id, report_id(FK), query_date, query_org, query_reason
```

### 设计原则
- 核心搜索/统计字段单独建列，扩展字段用 `data_json` 兜底
- 所有报告通过 `user_id` 隔离，用户只能访问自己的数据
- 保留原始文件路径，支持重新解析

---

## 七、API 接口设计

```
POST   /api/auth/login              # 登录，返回 JWT token
POST   /api/auth/register           # 注册（管理员操作）

POST   /api/reports/upload          # 上传文件，触发解析
GET    /api/reports                 # 获取当前用户报告列表
GET    /api/reports/{id}            # 获取报告完整解析结果
GET    /api/reports/{id}/download   # 下载解析结果 Excel
DELETE /api/reports/{id}            # 删除报告

GET    /api/users                   # 管理员查看所有用户（admin only）
```

---

## 八、前端页面设计（Streamlit）

```
app.py
├── pages/
│   ├── 1_上传解析.py    # 上传、解析进度、防篡改结果、下载Excel
│   ├── 2_报告列表.py    # 历史报告查询、筛选、删除
│   ├── 3_报告详情.py    # 分Tab展示各模块数据
│   └── 4_用户管理.py    # 管理员专用：添加/禁用用户
```

- 未登录时重定向登录页，token 存储在 `st.session_state`
- 报告详情页分 Tab 复用旧版展示逻辑

---

## 九、部署设计

### Web 版（VPS）
```
Nginx
├── /      → Streamlit :8501
└── /api   → FastAPI :8000

docker-compose 服务：
- fastapi
- streamlit
- postgresql
- glm-ocr（仅内网访问）
```

### 本地版（exe）
```
PyInstaller 打包
├── 内嵌 FastAPI（uvicorn）
├── 内嵌 Streamlit（自动打开浏览器）
├── SQLite 替代 PostgreSQL
└── GLM-OCR 独立安装（模型体积大，不内嵌）
```

### 配置切换
通过环境变量区分 `MODE=web|local`，数据库连接、OCR 地址等自动切换，业务代码完全共用。

---

## 十、项目目录结构

```
creditreport/
├── backend/
│   ├── api/
│   │   ├── auth.py         # 登录/注册接口
│   │   ├── reports.py      # 报告上传/查询/下载接口
│   │   └── users.py        # 用户管理接口
│   ├── parsers/
│   │   ├── base.py         # BaseParser 抽象类
│   │   ├── enterprise.py   # EnterpriseParser
│   │   ├── personal_detail.py
│   │   ├── personal_simple.py
│   │   └── factory.py      # ReportParserFactory
│   ├── ocr/
│   │   └── glm_ocr.py      # GLM-OCR 封装
│   ├── models/
│   │   └── db.py           # SQLAlchemy 模型
│   └── core/
│       ├── config.py       # 配置（web/local模式）
│       ├── auth.py         # JWT 工具
│       └── database.py     # 数据库连接
├── frontend/
│   ├── app.py
│   └── pages/
│       ├── 1_上传解析.py
│       ├── 2_报告列表.py
│       ├── 3_报告详情.py
│       └── 4_用户管理.py
├── creditreport_old/       # 旧代码（参考用）
├── docs/
│   └── superpowers/specs/
│       └── 2026-03-27-creditreport-design.md
└── deploy/
    ├── docker-compose.yml
    └── nginx.conf
```
