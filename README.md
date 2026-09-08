# VibeQA · 黑马程序员智能问答系统

基于 **RAG（Retrieval-Augmented Generation）** 的 IT 学习智能问答后端：文档语料 → Parent-Child 分块 → 向量化 → Milvus 检索 → 大模型生成。

- **LLM / 嵌入**：阿里云 DashScope（`qwen3.6-plus` + `text-embedding-v3`，在线调用）
- **向量库**：Milvus（`VibeQA/RAGQA`，1024 维 IVF_FLAT/COSINE）
- **业务库**：MySQL（会话与消息持久化）、Redis（预留缓存/限流）
- **框架**：FastAPI + SQLAlchemy + uv 管理

## 目录结构

```
app/
├── api/               # 路由：chat(即时+SSE)、conversations、meta(subjects/health)
├── clients/           # DashScope client（LLM 对话/流式 + 嵌入）
├── core/config.py     # 解析 config.ini → Settings
├── db/                # MySQL / Redis / Milvus client
├── models/            # SQLAlchemy ORM 表模型
├── rag/               # document_loader / chunker / retriever / greeting
├── services/          # qa(问答编排) / ingestion(语料入库)
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
cp .env.example .env                      # 填入真实 DASHSCOPE_API_KEY
# 数据库/向量库/模型等非敏感配置改 documents/data/config.ini
# 或用环境变量 EDURAG_CONFIG 指定其它 ini 路径
```

### 3. 建表 + 语料入库（可选，已将 ai_data 入库）

```bash
uv run python -m app.services.ingestion --dir documents/data/ai_data --subject ai [--reset] [--dry-run]
```

### 4. 启动

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# 交互文档: http://localhost:8000/docs
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

RAG 链路内部：问候语识别（命中则直接回复）→ query 嵌入 → Milvus 检索 → 子块按 `parent_chunk_id` 去重聚合取 Top `candidate_m` 父块 → 拼上下文 Prompt → LLM 生成。

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
