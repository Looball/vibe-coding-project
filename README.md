# VibeQA · 黑马程序员智能问答系统

基于 **RAG（Retrieval-Augmented Generation）** 的 IT 学习智能问答系统（后端 API + 原生前端）：文档语料 → Parent-Child 分块 → 混合检索 → 大模型生成。

- **LLM**：SiliconFlow（OpenAI 兼容在线）`deepseek-ai/DeepSeek-V4-Flash`
- **嵌入（dense）**：SiliconFlow 在线 `BAAI/bge-m3`（1024 维）
- **检索（sparse）**：Milvus 服务端 **BM25（jieba 分词）**，与 dense 组成**混合检索 + RRF 融合**
- **向量库**：Milvus（`VibeQA/RAGQA`：dense IVF_FLAT/COSINE + sparse SPARSE_INVERTED_INDEX/BM25）
- **业务库**：MySQL（会话/消息/文档/学科持久化）、Redis（预留缓存/限流）
- **框架**：FastAPI + SQLAlchemy + uv 管理；模型接口统一走 OpenAI 兼容 SDK

> 提示：嵌入/LLM 经 SiliconFlow 在线调用（`.env` 配置 base_url 与 key）；sparse 词法路依赖 Milvus 服务端 BM25 FUNCTION（需支持 jieba analyzer 的版本）。

## 目录结构

```
app/
├── api/               # 路由：chat(即时+SSE)、conversations、meta(subjects/health)
├── clients/           # 模型 client（DashScopeClient：LLM 对话/流式 + 嵌入，指向 .env 指定服务商）
├── core/config.py     # 解析 config.ini → Settings；.env 可覆盖 base_url/LLM/嵌入模型
├── db/                # MySQL / Redis / Milvus client（Milvus 为 hybrid schema）
├── models/            # SQLAlchemy ORM 表模型
├── rag/               # document_loader / chunker / retriever / greeting / query_rewrite / pipeline
├── services/          # qa(问答编排) / ingestion(语料入库)
frontend/              # 原生 SPA（首页/会话/学科选择，前后端分离）
tests/                 # 单元 + integration(pytest)
documents/data/        # PRD、技术设计、config.ini、ai_data 语料(不入库)
```

## 快速开始

### 1. 前置

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Docker：MySQL(3306)、Redis(6379)、Milvus(19530)（分别用各项目 `docker compose up -d`）

### 2. 配置

```bash
uv sync                                   # 安装依赖（含 dev）
cp .env.example .env                      # 填入服务商 key（当前为 SiliconFlow）

# 数据库/向量库/检索参数等非敏感配置：documents/data/config.ini
# 服务商与模型（可选覆盖，放 .env）：
#   DASHSCOPE_API_KEY   服务商 API key（必填）
#   DASHSCOPE_BASE_URL  如 https://api.siliconflow.cn/v1
#   LLM_MODEL           如 deepseek-ai/DeepSeek-V4-Flash
#   EMBEDDING_MODEL     如 BAAI/bge-m3
# 其它 ini 路径：环境变量 EDURAG_CONFIG
```

### 3. 建表 + 语料入库（可选，已将 ai_data 入库）

```bash
uv run python -m app.services.ingestion --dir documents/data/ai_data --subject ai [--reset] [--dry-run]
```

### 4. 启动

```bash
# 后端 API（前后端分离，后端只提供 /api/v1）
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# 交互文档: http://localhost:8000/docs

# 前端（独立静态服务，默认指向 http://localhost:8000）
uv run python -m http.server 8080 -d frontend
# 页面: http://localhost:8080
# 改后端地址: 编辑 frontend/index.html 里 window.__VIBEQA__.api

# 可选：单进程一键模式（后端代托管前端）
VIBEQA_SERVE_FRONTEND=1 uv run uvicorn main:app --port 8000
# 页面与文档都在 http://localhost:8000
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/chat` | 即时回答 `{query, subject?}` |
| POST | `/api/v1/chat/stream` | 流式回答（SSE：`sources`→`message`…→`done`） |
| POST | `/api/v1/conversations` | 创建会话 |
| GET | `/api/v1/conversations` | 会话列表（新在前，含消息数） |
| POST | `/api/v1/conversations/{id}/messages` | 发消息并持久化（user+assistant） |
| GET | `/api/v1/conversations/{id}/messages` | 消息历史（倒序，支持 limit/offset） |
| DELETE | `/api/v1/conversations/{id}` | 清除会话（级联消息，返回 204） |
| GET | `/api/v1/subjects` | 学科列表（ai/java/test/ops/bigdata…） |
| GET | `/api/v1/health` | 健康检查（mysql/redis/milvus 探活） |

RAG 核心流程（`app/rag/pipeline.py` 编排）：
问候语识别（命中直接回复）→（可选）**LLM Query 改写** → query 嵌入 →
**混合检索**（dense bge-m3 + 服务端 BM25/jieba，RRF 融合）→ 子块按 `parent_chunk_id`
去重、取最高分聚合重排取 Top `candidate_m` 父块 → 拼上下文 Prompt → LLM 生成（即时/SSE）。

命令行演示完整流程：

```bash
uv run python -m app.rag.pipeline "什么是大语言模型" --subject ai     # 关闭改写加 --no-rewrite
```

## 测试与验证

```bash
./init.sh                     # 标准启动验证（语法/导入/配置/服务探测/pytest）
uv run python -m pytest       # 离线单元测试
uv run python -m pytest -m integration   # 需要 MySQL/Redis/Milvus 在线
```

> 代理协作说明：仓库根有 `CLAUDE.md`（开工流程/架构/环境依赖）、`feature_list.json`（功能状态）、`progress.md`（会话进度日志）、`session-handoff.md`（交接）。任意 coding agent 均可在开工前读取、交接前更新。

## 文档

- 产品需求：`documents/data/product_requirement_document.md`
- 技术设计：`documents/data/technical_design_document.md`
