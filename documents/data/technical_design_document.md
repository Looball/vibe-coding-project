# 黑马程序员智能问答系统技术设计文档 (TDD)

## 1. 系统架构概述

### 1.1 架构模式

本系统采用 **RAG（Retrieval-Augmented Generation）** 架构，结合大语言模型与向量检索技术，实现高准确率的智能问答。整体架构分为以下四层：

| 层级 | 说明 | 技术选型 |
|------|------|---------|
| **应用层** | 用户交互界面与 API 网关 | FastAPI + WebSocket |
| **检索层** | 向量检索与重排序 | Milvus + 混合检索 |
| **模型层** | 嵌入模型 + 大语言模型 | DashScope (阿里云) |
| **数据层** | 知识库存储与缓存 | MySQL + Redis + Milvus |

### 1.2 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                    应用层                            │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Web 前端     │  │  API 网关    │  │ WebSocket │  │
│  │  (Vue/React)  │  │  (FastAPI)   │  │  流式响应  │  │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘  │
└─────────┼─────────────────┼─────────────────┼────────┘
          │                 │                 │
┌─────────┼─────────────────┼─────────────────┼────────┐
│         │           检索层                     │        │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴─────┐  │
│  │  query 改写   │  │  向量检索    │  │  重排序    │  │
│  │  (LLM)       │  │  (Milvus)    │  │  (RRF)     │  │
│  └──────────────┘  └──────────────┘  └────────────┘  │
│                ┌────────────────────┐                 │
│                │   Parent-Child 检索  │                 │
│                └────────────────────┘                 │
└───────────────────────────────────────────────────────┘
          │                 │                 │
┌─────────┼─────────────────┼─────────────────┼────────┐
│   模型层 └─────────┐       │                 │        │
│  ┌─────────────────┴──────────────────┐              │
│  │     阿里云 DashScope API            │              │
│  │  ┌──────────────┐  ┌────────────┐  │              │
│  │  │ 嵌入模型      │  │ LLM 模型   │  │              │
│  │  │ (text-embed  │  │ (qwen3.6  │  │              │
│  │  │  -v3)        │  │  -plus)    │  │              │
│  │  └──────────────┘  └────────────┘  │              │
│  └────────────────────────────────────┘              │
└───────────────────────────────────────────────────────┘
          │                 │                 │
┌─────────┼─────────────────┼─────────────────┼────────┐
│         │           数据层                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │    MySQL      │  │    Redis     │  │   Milvus   │ │
│  │  学科知识图谱  │  │  会话缓存    │  │  向量数据库 │ │
│  │  用户/会话    │  │  限流计数    │  │  文档切片   │ │
│  └──────────────┘  └──────────────┘  └────────────┘ │
└───────────────────────────────────────────────────────┘
```

---

## 2. RAG 核心技术方案

### 2.1 RAG 流程总览

```
用户提问
    │
    ▼
┌──────────────────────┐
│  1. Query 处理        │
│  ├─ 问候语识别 ─→ 直接回答      │
│  ├─ 学科分类 ─→ 过滤检索范围    │
│  └─ Query 改写 (LLM) ─→ 优化检索 │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  2. 向量检索          │
│  ├─ Query 嵌入化      │
│  ├─ Milvus ANN 检索   │
│  │  (retrieval_k=10)  │
│  └─ 返回候选文档       │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  3. 重排序 & 融合     │
│  ├─ RRF 分数融合      │
│  ├─ 候选精选 (candidate_m=3) │
│  └─ 组装上下文         │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  4. LLM 生成          │
│  ├─ 组装 Prompt       │
│  ├─ 流式 / 即时输出   │
│  └─ 返回最终答案       │
└──────────────────────┘
```

### 2.2 Parent-Child 分块策略

采用 **Parent-Child 分块** 策略，平衡检索精度与上下文完整性：

| 参数 | 值 | 说明 |
|------|-----|------|
| `parent_chunk_size` | 1200 tokens | 父块大小，作为最终上下文单位 |
| `child_chunk_size` | 300 tokens | 子块大小，作为检索单位 |
| `chunk_overlap` | 50 tokens | 块间重叠，防止语义断裂 |

**流程说明**：
1. 文档先切分为 Parent Chunks（1200 tokens）
2. 每个 Parent Chunk 再切分为多个 Child Chunks（300 tokens）
3. Child Chunks 生成向量存入 Milvus
4. 检索时匹配 Child Chunks，返回所属的 Parent Chunk 作为上下文
5. Parent Chunk 送入 LLM 生成最终答案

### 2.3 检索参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `retrieval_k` | 10 | 检索返回的候选文档数 |
| `candidate_m` | 3 | 最终精选的上下文块数 |
| 索引类型 | IVF_FLAT | Milvus 索引类型 |
| 距离度量 | COSINE | 余弦相似度 |

---

## 3. 数据存储设计

### 3.1 MySQL 数据库设计

**数据库名**: `subjects_kg`

#### 学科知识图谱表

```sql
-- 学科表
CREATE TABLE subjects (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(50)  NOT NULL COMMENT '学科名称',
    code        VARCHAR(20)  NOT NULL UNIQUE COMMENT '学科编码',
    description TEXT         COMMENT '学科描述',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 知识点表
CREATE TABLE knowledge_points (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    subject_id  INT          NOT NULL COMMENT '所属学科',
    title       VARCHAR(200) NOT NULL COMMENT '知识点标题',
    content     TEXT         COMMENT '知识点内容',
    parent_id   INT          DEFAULT NULL COMMENT '父知识点ID',
    level       INT          DEFAULT 0 COMMENT '层级',
    sort_order  INT          DEFAULT 0 COMMENT '排序',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (parent_id)  REFERENCES knowledge_points(id)
);

-- 文档表
CREATE TABLE documents (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    subject_id  INT          NOT NULL COMMENT '所属学科',
    title       VARCHAR(200) NOT NULL COMMENT '文档标题',
    file_path   VARCHAR(500) COMMENT '文件路径',
    file_type   VARCHAR(20)  COMMENT '文件类型(pdf/docx/md)',
    chunk_count INT          DEFAULT 0 COMMENT '分块数',
    status      TINYINT      DEFAULT 0 COMMENT '0=待处理 1=已处理 2=失败',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);
```

#### 会话与用户表

```sql
-- 会话表
CREATE TABLE conversations (
    id          VARCHAR(36)  PRIMARY KEY COMMENT '会话UUID',
    title       VARCHAR(100) COMMENT '会话标题',
    subject_id  INT          COMMENT '当前学科过滤',
    status      TINYINT      DEFAULT 1 COMMENT '0=关闭 1=活跃',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

-- 消息表
CREATE TABLE messages (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id VARCHAR(36)  NOT NULL,
    role            ENUM('user', 'assistant') NOT NULL,
    content         TEXT         NOT NULL,
    sources         JSON         COMMENT '引用的文档来源',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
```

### 3.2 Milvus 向量数据库设计

**配置**:
- `database_name` = `itcast`
- `collection_name` = `edurag_bj29`

#### Collection Schema

```python
collection_schema = {
    "fields": [
        {"name": "id",           "type": DataType.INT64,    "is_primary": True, "auto_id": True},
        {"name": "chunk_id",     "type": DataType.VARCHAR,  "max_length": 64},
        {"name": "parent_chunk_id", "type": DataType.VARCHAR, "max_length": 64},
        {"name": "document_id",  "type": DataType.INT64},
        {"name": "subject_code", "type": DataType.VARCHAR,  "max_length": 20},
        {"name": "chunk_text",   "type": DataType.VARCHAR,  "max_length": 2000},
        {"name": "embedding",    "type": DataType.FLOAT_VECTOR, "dim": 1024},
        {"name": "metadata",     "type": DataType.JSON},
    ],
    "index": {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 1024}
    }
}
```

#### 数据写入流程

```
文档 → 解析 → Parent Chunk(1200t) → Child Chunk(300t) → 嵌入化 → 写入 Milvus
                                                              │
                                                              ▼
                                                        存储关联关系
                                                  (parent_chunk_id映射)
```

### 3.3 Redis 缓存设计

| Key 模式 | 用途 | TTL | 数据结构 |
|----------|------|-----|---------|
| `session:{id}` | 会话状态 | 30min | Hash |
| `rate_limit:{ip}` | 接口限流 | 1min | Sorted Set |
| `cache:knowledge:{subject}` | 知识缓存 | 1h | String(JSON) |
| `queue:embedding` | 嵌入任务队列 | - | List |

---

## 4. 嵌入模型方案

### 4.1 模型选择

**服务商**: 阿里云 DashScope  
**模型**: `text-embedding-v3`（在线调用）  
**向量维度**: 1024

### 4.2 API 调用集成

所有 LLM 和嵌入模型调用均通过 **阿里云 DashScope API** 完成，使用兼容 OpenAI 格式的接口地址：

```
base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 4.3 嵌入流程

```python
# 伪代码示例
from openai import OpenAI

client = OpenAI(
    api_key="your-dashscope-api-key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 文本嵌入
response = client.embeddings.create(
    model="text-embedding-v3",
    input="需要嵌入的文本"
)
embedding = response.data[0].embedding  # 1024维向量
```

### 4.4 优势

- **免运维**: 无需自建嵌入服务，降低运维成本
- **高精度**: 阿里云 text-embedding-v3 在多个中文基准上表现优异
- **弹性扩展**: 按需调用，随业务增长自动扩展

---

## 5. LLM 模型方案

### 5.1 模型配置

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | `qwen3.6-plus` | 阿里云通义千问 |
| 接口 | DashScope 兼容 OpenAI 格式 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 调用方式 | 支持流式 (SSE) 和即时返回 | 通过 `stream=True/False` 控制 |

### 5.2 Prompt 模板设计

#### 学科问答模板

```
你是一个 {subject} 学科的智能助教，请基于以下参考资料回答学生的问题。

参考资料：
{context}

学生问题：{query}

要求：
1. 如果参考资料中有相关信息，请基于资料回答
2. 如果参考资料中无相关信息，请如实告知"暂未找到相关答案"
3. 回答应简洁、准确、条理清晰
4. 使用中文回答

回答：
```

#### 问候语识别模板

```
判断用户输入是否为日常问候语（如"你好"、"早上好"、"谢谢"等）。
如果是，请返回 friendly 回应；如果不是，请返回 academic。

用户输入：{query}
分类结果：
```

---

## 6. API 接口设计

### 6.1 接口列表

| 方法 | 路径 | 说明 | 适用功能 |
|------|------|------|---------|
| POST | `/api/v1/chat` | 即时回答 | 2.2.2.1 |
| POST | `/api/v1/chat/stream` | 流式回答(SSE) | 2.2.2.2 |
| GET | `/api/v1/conversations` | 会话列表 | 2.1.2.2 |
| POST | `/api/v1/conversations` | 创建会话 | 2.1.2.1 |
| POST | `/api/v1/conversations/{id}/messages` | 发送消息 | 2.2.1 |
| GET | `/api/v1/conversations/{id}/messages` | 消息历史 | 2.1.2.2 |
| DELETE | `/api/v1/conversations/{id}` | 清除会话 | 2.1.2.3 |
| GET | `/api/v1/subjects` | 学科列表 | 2.3.2 |
| GET | `/api/v1/health` | 健康检查 | 2.3.1 |

### 6.2 流式回答接口格式

```json
// POST /api/v1/chat/stream
// Request
{
    "conversation_id": "uuid",
    "query": "什么是神经网络？",
    "subject": "ai",
    "mode": "stream"
}

// Response (SSE)
data: {"type": "token", "content": "神经"}
data: {"type": "token", "content": "网络"}
data: {"type": "token", "content": "是..."}
data: {"type": "sources", "content": [{"doc_id": 1, "title": "深度学习基础"}]}
data: {"type": "done"}
```

---

## 7. 学科管理

系统支持以下学科，定义在 `config.ini` 的 `[app]` 节：

| 学科编码 | 说明 |
|---------|------|
| `ai` | 人工智能 |
| `java` | Java 开发 |
| `test` | 软件测试 |
| `ops` | 运维 |
| `bigdata` | 大数据 |

检索时，Milvus 通过 `subject_code` 字段进行过滤，实现学科范围限定。

---

## 8. 组件依赖与配置清单

### 8.1 环境依赖

| 组件 | 版本要求 | 用途 |
|------|---------|------|
| Python | 3.10+ | 后端开发语言 |
| Milvus | 2.4+ | 向量数据库 |
| MySQL | 8.0+ | 关系型数据库 |
| Redis | 7.0+ | 缓存与队列 |
| FastAPI | 0.110+ | API 框架 |
| pymilvus | 2.4+ | Milvus Python SDK |
| openai | 1.0+ | DashScope API 调用 |

### 8.2 配置清单

完全覆盖 `config.ini` 中的所有配置项，详见 [config.ini](config.ini)。

---

## 9. 性能指标

| 指标 | 目标值 | 对应 PRD 要求 |
|------|--------|------------|
| 页面加载 | < 2s | 4.2 |
| 简单问答 | < 2s | 4.2 |
| 复杂问答 | < 5s | 4.2 |
| 问题理解准确率 | > 85% | 2.2.1 |
| 向量检索延迟 | < 500ms | - |
| 并发支持 | 100+ QPS | - |

---

## 10. 部署架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Nginx      │ ──▶ │  FastAPI     │ ──▶ │   Milvus     │
│  反向代理     │     │  API服务      │     │   向量库      │
│  负载均衡     │     │  (多实例)     │     └──────────────┘
└──────────────┘     │              │     ┌──────────────┐
                     │              │ ──▶ │   MySQL      │
                     │              │     │  关系型库     │
                     │              │     └──────────────┘
                     │              │     ┌──────────────┐
                     │              │ ──▶ │   Redis      │
                     └──────────────┘     │  缓存        │
                                          └──────────────┘
```

---

## 11. 附录

### 11.1 技术栈总结

| 类别 | 技术 | 选型理由 |
|------|------|---------|
| 框架 | FastAPI | 异步支持好，天然适配 SSE 流式响应 |
| 向量库 | Milvus | 高性能向量检索，支持标量过滤 |
| 嵌入模型 | DashScope text-embedding-v3 | 在线调用，免运维，高精度中文嵌入 |
| LLM | DashScope qwen3.6-plus | 阿里云大模型，支持流式输出 |
| 关系库 | MySQL | 成熟稳定，存储知识图谱关系 |
| 缓存 | Redis | 会话管理、限流、任务队列 |

### 11.2 与 PRD 需求映射

| PRD 章节 | 功能 | 技术实现 |
|---------|------|---------|
| 2.1.1 | 首页访问 | FastAPI + Vue/React 前端 |
| 2.1.2 | 会话管理 | Redis 会话缓存 + MySQL 持久化 |
| 2.2.1 | 问答查询 | RAG 检索 + LLM 生成 |
| 2.2.2.1 | 即时回答 | OpenAI 同步 API |
| 2.2.2.2 | 流式回答 | SSE + OpenAI 流式 API |
| 2.2.3 | 智能识别 | LLM Prompt 分类 |
| 2.2.4 | 学科过滤 | Milvus 标量过滤 |
| 2.3.1 | 系统监控 | FastAPI 健康检查端点 |
| 2.3.2 | 学科管理 | MySQL 学科表 + API |