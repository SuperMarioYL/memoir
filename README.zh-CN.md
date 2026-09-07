[English](./README.md) | **简体中文**

# Memoir

> 一个能记住你一生的消费级 AI —— 依托 DeepSeek 前缀缓存，成本足够低。

你的个人 AI 总是健忘，因为每一轮对话都要把你的完整历史重新发一遍，在 OpenAI/Claude 上代价太高。Memoir 把你的笔记拼装成一个**缓存稳定的个人历史前缀**，每轮都把这份完整前缀重新发给 DeepSeek API，前缀缓存的折扣让"全量记忆"从每轮数美元降到几美分。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/flow-dark.svg">
  <img src="./assets/flow-light.svg" alt="Memoir 架构：把笔记文件夹摄入为缓存稳定的前缀，每轮重新发送到 DeepSeek 前缀缓存。">
</picture>

## 演示

以下是 `examples/notes`（4 篇小笔记）的真实输出。按下方"快速开始"即可复现——`ingest` 与 `cost` 完全离线运行；`chat` 需要 DeepSeek API key。

```
$ memoir ingest examples/notes
             Ingested 4 note(s)
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┓
┃ Source               ┃ Kind     ┃ Tokens ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━┩
│ 2024-goals.md        │ markdown │     44 │
│ decision-deepseek.md │ markdown │    118 │
│ reading-list.md      │ markdown │     72 │
│ training.txt         │ text     │     82 │
└──────────────────────┴──────────┴────────┘

Prefix assembled. tokens=346  sources=4  hash=7dfc31cffa444112  cache_stable=True

$ memoir cost
         Per-turn cost — prefix 346 tokens, ~300 output tokens
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Provider      ┃ Assumption                               ┃ Per turn ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ DeepSeek      │ cache hit (steady state) — deepseek-chat │  $0.0004 │
│ DeepSeek      │ cache miss (first turn)                  │  $0.0004 │
│ OpenAI gpt-4o │ no prompt caching                        │  $0.0039 │
│ OpenAI gpt-4o │ with prompt caching (~50% off cached)    │  $0.0034 │
└───────────────┴──────────────────────────────────────────┴──────────┘
Savings: OpenAI no-cache minus DeepSeek steady-state = $0.0035/turn (11x cheaper on DeepSeek)
```

前缀在多次运行间逐字节一致（重新 ingest 后用 `shasum` 校验过），这正是触发 DeepSeek 前缀缓存折扣所需的"缓存稳定"性质。

```
$ export DEEPSEEK_API_KEY=sk-...
$ memoir chat
Memoir chat — model deepseek-chat, prefix loaded. Type your question; Ctrl-D or 'exit' to quit.

you> Which books changed how I work, and what pace do I need to break 2:00?
memoir> The Mom Test changed how you interview users. You need 5:40/km for 21k to break 2:00; you're at 5:45/km now.
DeepSeek prefix-cache: $0.0004/turn  OpenAI equivalent: $0.0039/turn
```

（上面这轮对话用于说明已发布的 `memoir chat` 流程，需要真实的 `DEEPSEEK_API_KEY`。成本行由 API 返回的 `usage` 实际数据计算，费率与 `memoir cost` 一致。）

## 安装

需要 Python 3.12+。

```bash
# 从源码安装（克隆）
git clone https://github.com/SuperMarioYL/memoir.git
cd memoir
uv pip install -e .        # 或：pip install -e .

# 或发布后一行安装
uv tool install memoir     # 或：pipx install memoir
```

设置 DeepSeek API key（在 <https://platform.deepseek.com> 获取）：

```bash
export DEEPSEEK_API_KEY=sk-...
```

## 快速开始

```bash
# 1. 把 Memoir 指向任意存放 .md / .txt 笔记的文件夹
memoir ingest ~/Notes

# 2. 看看你的实际前缀对应的费用对比
memoir cost

# 3. 与一个读过你全部笔记的 AI 对话
memoir chat
```

其他命令：

```bash
memoir status        # 概览 manifest 与会话
memoir chat --reset  # 开启全新对话（前缀不受影响）
```

状态文件位于 `~/.memoir/`（`prefix.txt`、`manifest.yaml`、`session.json`）。
用 `MEMOIR_HOME=/some/dir` 覆盖目录位置，用 `DEEPSEEK_MODEL=deepseek-chat` 覆盖模型，
用 `DEEPSEEK_BASE_URL=https://api.deepseek.com` 覆盖 API 地址。

## 工作原理

### 新原语：缓存稳定的个人历史前缀

状态是模型的对手：跨会话时模型本身是无状态的，要记住你的一生，就必须**每轮都把完整个人历史重新发一遍**。在按 token 计费下这代价高得离谱，所以市面上的个人 AI 产品（ChatGPT Memory、Claude Projects）都退而求其次做摘要或 RAG 检索——用召回质量换成本。

DeepSeek 的前缀缓存对"重复的前缀 token"打折。Memoir 把这一点变成一个消费级原语：它把你的笔记拼装成一个**跨会话逐字节一致**的前缀，使同一份前缀命中 DeepSeek 缓存，并在首轮之后每一轮都按缓存价计费。

它不是 RAG（不做检索、不用 embedding），也不是摘要（历史原文整段发出）。

### 磁盘布局

```
~/.memoir/
├── prefix.txt        # 拼装好的、有序的个人历史
├── manifest.yaml     # source_count、total_tokens、prefix_hash、cache_stable、sources[]
└── session.json      # 当前会话的对话轮次
```

### 为什么前缀是"缓存稳定"的

- **确定性排序**——按 `(相对路径, 内容哈希)` 排序，拼出的前缀与文件系统遍历顺序、与运行的机器都无关，逐字节一致。
- **稳定框架**——每篇笔记用相同的头部标记包裹，单篇正文长度变化不会让前缀文本整体错位。
- **摄入时校验**——`cache_stable=True` 表示"重新排序并重新拼装后得到逐字节一致的前缀"。将来若某次改动破坏了确定性，这个标记会变 False，缓存折扣会悄无声息地失效——这一校验就是为了让那种情况被立刻发现。

### 架构

单个 Python 进程。`ingest.py` 读取笔记文件夹；`prefix.py` 拼装缓存稳定的前缀并写出 manifest；`session.py` 管理对话轮次；`deepseek_client.py` 把 `前缀 + 轮次` 发给 DeepSeek 并解析缓存命中的 `usage`；`cost.py` 为同一轮对话算出 OpenAI 等价成本；`cli.py` 把它们串起来。没有微服务、没有常驻进程、没有独立的推理服务器。

### v0.1 刻意不做的事

- 仅 CLI——不做网页/桌面 GUI。
- 仅 DeepSeek——不做多模型。
- 仅本地文件夹——不做 Notion/Apple Notes API 自动同步。
- 仅全量上下文——不做向量检索 / RAG 回退。
- 不做"对话折叠"（轮次不回写到持久前缀里）。
- 不做落盘加密。

## 价格

Memoir 本身免费开源。你用自己的 API key 直接向 DeepSeek 付费。下表是 Memoir 计算所用的公开费率快照（2026-09；引用前请到各家官网复核）。

| 服务商 | 输入（缓存未命中） | 输入（缓存命中） | 输出 | 来源 |
|---|---|---|---|---|
| DeepSeek `deepseek-chat`（V3） | $0.27 / 1M | **$0.07 / 1M** | $1.10 / 1M | [DeepSeek 定价](https://api-docs.deepseek.com/quick_start/pricing) |
| OpenAI `gpt-4o` | $2.50 / 1M | $1.25 / 1M（prompt cache，约 5 折） | $10.00 / 1M | [OpenAI 定价](https://openai.com/api/pricing/) |

**算例——2 万 token 的一生体量前缀，每轮 300 token 回复。** 这是按上表费率做的示例，不是实测基准。你的真实数字请用 `memoir cost` 针对实际前缀查看。

| 每轮 | DeepSeek（缓存命中） | DeepSeek（首轮未命中） | OpenAI（无缓存） | OpenAI（prompt cache） |
|---|---|---|---|---|
| 成本 | **约 $0.0017** | 约 $0.0057 | 约 $0.053 | 约 $0.028 |

按 2 万 token 前缀每月约 200 轮算，DeepSeek 稳态大概 **$0.35/月** 的 API 成本——这正是"一生记忆"终于负担得起的根本原因。同样用量在 GPT-4o 不开缓存时约 $10.60/月，即便开 prompt cache 也约 $5.60/月（且要求缓存能在轮次间存活，对零散的消费级使用往往做不到）。

**未来：Memoir Cloud。** 开源 CLI 免费且本地运行、用你自己的 key。未来的托管层（约 $12/月）会代你管理前缀、汇集 API 成本、免去碰 API key 和终端——这是 OSS 内核之上自然的 SaaS 层，不是画饼。v0.1 只发布 CLI。

## 常见问题

**这不就是把 ChatGPT Memory 换个更便宜的模型吗？**
不是。ChatGPT Memory 做摘要并 RAG 检索片段；Memoir 每轮把完整个人历史重新发出，追求全量召回。成本差异是结构性的——只有前缀缓存折扣才让"全量重发"负担得起。

**为什么不对笔记直接做 RAG？**
RAG 检索片段，会丢掉跨笔记的综合判断。问"我在所有笔记里对 X 做了哪些决定"，RAG 可能漏掉那个跨笔记的模式。Memoir 每轮全发。

**把全部个人数据发给 DeepSeek 有隐私风险。**
这是个真实的取舍。v0.1 在本地拼装前缀、用你自己的 key——笔记只为推理发出，不存储。落盘加密和本地模型支持在 v0.2。

**万一 OpenAI/Anthropic 也推前缀缓存折扣？**
成本优势会收窄，但 Memoir 占着消费级品牌和"个人历史摄入"这套交互。成本原语是入场的楔子，不是唯一护城河。

**为什么不直接用 DeepSeek？**
DeepSeek API 不会把你的笔记拼装成缓存稳定的前缀，也不会管理"每轮重发"这个模式。Memoir 是这一原语之上的消费层。

**token 数精确吗？**
摄入时 Memoir 用 `tiktoken`（`cl100k_base`）做估算写入 manifest。`chat` 期间 DeepSeek API 返回权威的 `usage` 计数（含 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`），打印的成本行就用这些真实数据。

## 参与贡献

v0.1 是一个范围刻意收窄的 CLI。欢迎提 bug 与小修。更大的功能（GUI、多模型、对话折叠、加密、托管层）不在 v0.1 范围内——大改请先开 issue 讨论。

```bash
git clone https://github.com/SuperMarioYL/memoir.git
cd memoir
uv pip install -e .
pytest -q
```

## 许可证

MIT —— Copyright (c) 2026 SuperMarioYL。详见 [LICENSE](./LICENSE)。
