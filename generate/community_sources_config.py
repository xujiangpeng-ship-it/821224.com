# -*- coding: utf-8 -*-
"""
社区视角（community-perspectives）数据源池配置
================================================
调研对象：last30days-skill 的 19 个源（https://github.com/mvanhorn/last30days-skill）。
站点垂直：保险 / Insurtech（英文站 821224.com）。

设计原则
--------
1. 不整体接管 last30days 引擎（它是 agent 交互型 CLI，JSON schema 不完整、解析脆弱，
   且产出是"AI 综合简报"而非真人内容）。只复用其"哪些源免费/怎么取"的知识，
   自己写轻量 fetcher（见 community_sources.py）。
2. 只保留与保险/Insurtech 主题相关的源；社媒/B2C 源（TikTok/IG/Threads/Pinterest/
   Amazon/小红书/TruthSocial）首期跳过。
3. 统一抽取成 Quote schema: {source, author, score, text, url, date, topic}，
   再经相关性+垃圾过滤，取 3-5 条渲染成"社区视角"区块。

tier 含义
---------
1 = 高价值 + 已验证可用或可低成本接入（HN 已验证；Reddit 需解决访问）
2 = 免费但需装 CLI / 仅特定子主题激活
3 = 需付费 key 但价值高（LinkedIn、X 可走免费路径）
skip = 与主题无关，不进池子
"""

# ---------------------------------------------------------------------------
# 源池：每个源怎么拉、能不能直接用
# ---------------------------------------------------------------------------
SOURCE_POOL = {
    "hackernews": {
        "tier": 1,
        "auth": "none",
        "cost": "free",
        "directly_usable": True,
        "pull": "HN Algolia API: https://hn.algolia.com/api/v1/search?query=<q>&tags=comment",
        "default_subs": [],
        # 2026-09-01 实测：可用，且能取到当天评论（时效最好）。
        # 噪声：query=insurance 会召回招聘帖（"Multiple Engineering + Product Roles"）
        # 和只是顺带提到 insurance 的无关讨论 -> 必须做招聘帖过滤 + 主题相关性判断。
        "notes": "唯一稳定可用的主力源，时效到当天。适合技术类 Insurtech / AI-理赔辩论。",
    },
    "reddit": {
        "tier": 1,
        "auth": "Reddit OAuth app 或 ScrapeCreators key(10k 免费)",
        "cost": "free tier",
        # 2026-09-01 实测（本机代理出口）：
        #   reddit.com / old.reddit.com -> 403 Blocked（数据中心 IP 被封）
        #   OAuth app 的创建本身就要登录 reddit.com，用户同样打不开 -> 此路不通
        #   绕行通道：
        #     pullpush.io 评论归档 -> 能通，但归档截止 2025-05（过期一年多），
        #                            且限流极严（连续第二次请求即 429）
        #     teddit.net -> SSL 错误；libreddit 镜像 -> 403，均已废弃
        # 2026-09-01（晚些）：用户提供的 ScrapeCreators key 验证通过。
        #   POST/GET /v1/reddit/search           -> 200，返回真实且新鲜的帖子
        #   GET /v1/reddit/post/comments?url=... -> 200，可取到高赞评论
        # 注意：search 端点的 subreddit 参数无效（指定后仍返回全局结果），
        #       必须在客户端按 subreddit 过滤（见 community_sources._sub_ok）。
        "directly_usable": True,
        "auth_env": "SCRAPECREATORS_API_KEY",
        "pull": "/v1/reddit/search + /v1/reddit/post/comments",
        "default_subs": [
            "Insurance", "InsuranceAdjusters", "InsuranceProfessional",
            "Insurtech", "legaladvice", "personalfinance",
        ],
        "notes": "价值最高的源，已通过 ScrapeCreators 打通。每篇约 2-3 credit。",
    },
    "trustpilot": {
        "tier": 1,
        "auth": "free CLI: trustpilot-pp-cli (opt-in)",
        "cost": "free",
        "directly_usable": True,
        "opt_in": True,
        "pull": "品牌评价搜索（按域名/公司名）",
        "default_subs": [],
        "notes": "适合'真实用户怎么说'段落；按文章涉及的保险公司/Insurtech 品牌触发。",
    },
    "dripstack": {
        "tier": 1,
        "auth": "none (公开搜索 API, opt-in)",
        "cost": "free",
        "directly_usable": True,
        "opt_in": True,
        "pull": "付费财经 newsletter / 分析师文章检索",
        "default_subs": [],
        "notes": "Insurtech 分析师观点稀缺来源，强烈推荐常开。",
    },
    "linkedin": {
        "tier": 3,
        "auth": "ScrapeCreators key (10k 免费)",
        "cost": "free tier",
        "directly_usable": False,
        "pull": "帖子 + 文章（B2B 思想领袖，E-E-A-T 最强）",
        "default_subs": [],
        "notes": "价值高但需付费 key；首期可暂不接，等 Reddit/HN/Trustpilot 跑顺再加。",
    },
    "github": {
        "tier": 2,
        "auth": "gh CLI (免费)",
        "cost": "free",
        "directly_usable": True,
        "pull": "仓库 issue/PR 搜索（开放保险 API 实现、开源 Insurtech）",
        "default_subs": [],
        "notes": "仅技术类文章（开放保险 API）触发。",
    },
    "polymarket": {
        "tier": 2,
        "auth": "none",
        "cost": "free",
        "directly_usable": True,
        "pull": "预测市场（监管/气候/保险政策）",
        "default_subs": [],
        "notes": "稀有点，适合监管/政策类 hook。",
    },
    "arxiv": {
        "tier": 2,
        "auth": "arxiv-pp-cli (免费)",
        "cost": "free",
        "directly_usable": True,
        "pull": "AI/ML/精算论文",
        "default_subs": [],
        "notes": "反欺诈、LLM 在保险应用的学术引用。",
    },
    "techmeme": {
        "tier": 2,
        "auth": "techmeme-pp-cli (免费)",
        "cost": "free",
        "directly_usable": True,
        "pull": "科技新闻实时归档",
        "default_subs": [],
        "notes": "Insurtech 融资/裁员新闻。",
    },
    "digg": {
        "tier": 2,
        "auth": "digg-pp-cli (免费)",
        "cost": "free",
        "directly_usable": True,
        "pull": "热点新闻聚合",
        "default_subs": [],
        "notes": "通用保险热点补充。",
    },
    "stocktwits": {
        "tier": 2,
        "auth": "none (公开 API, 仅股票/加密主题自动激活)",
        "cost": "free",
        "directly_usable": True,
        "pull": "股价/情绪讨论",
        "default_subs": [],
        # 实测：AIG 单次可取 30 条；但连续请求会被限流（返回非 JSON），
        # 必须低频调用 + 捕获非 JSON 响应。
        "notes": "仅当文章含 ticker/上市公司时激活；限流明显，低频使用。",
    },
    "bluesky": {
        "tier": 2,
        "auth": "BSKY_HANDLE + BSKY_APP_PASSWORD (免费)",
        "cost": "free",
        "directly_usable": False,  # 实测 public.api.bsky.app 在本环境 403
        "pull": "帖子搜索",
        "default_subs": [],
        "notes": "2026-09-01 实测：公共 AppView 端点持续 403，本环境不可用。",
    },
    "youtube": {
        "tier": 2,
        "auth": "yt-dlp (免费)",
        "cost": "free",
        "directly_usable": True,
        "pull": "视频 + 评论（会议演讲/反欺诈案例）",
        "default_subs": [],
        "notes": "评论走 yt-dlp 免费；仅视频型/案例型文章触发。",
    },
    "x": {
        "tier": 3,
        "auth": "grok CLI (无凭据) 或 AUTH_TOKEN+CT0 Cookie (免费) 或 XAI_API_KEY",
        "cost": "free path available",
        "directly_usable": False,
        "pull": "推文搜索",
        "default_subs": [],
        "notes": "Insurtech 创始人/分析师高频发声；免费路径需登录态，管线里最好用 grok CLI 或 Cookie。",
    },
}

# 明确跳过的源
SKIP_SOURCES = [
    "tiktok", "instagram", "threads", "pinterest",   # B2C 社媒，保险无意义
    "amazon",                                        # 商品评论，非核心
    "xiaohongshu", "truthsocial",                    # 与英文保险站无关
    "telegram",                                      # 需指定频道 handle，首期不做
    "perplexity",                                    # AI 研究引擎，非真人内容
    # ---- 2026-09-01 实测后追加 ----
    "quora",                                         # 403，本环境不可达
    "teddit", "libreddit",                           # Reddit 镜像，已废弃
    "pullpush",                                      # Reddit 归档：数据止于 2025-05 且限流严
    "stackexchange",                                 # 内容偏消费者个人理财 + 年份停在 2014-2023
    "mastodon",                                      # mastodon.social 搜 insurance 返回 0 条
]

# ---------------------------------------------------------------------------
# 子主题 → 源分配（hook 抽取后按此路由）
# ---------------------------------------------------------------------------
THEME_TO_SOURCES = {
    # 2026-09-01 按实测可达性重排；Reddit 经 ScrapeCreators 打通后已并回。
    "ai_claims":            ["reddit", "hackernews", "techmeme"],
    "ai_fraud":             ["reddit", "hackernews", "polymarket"],
    "embedded_insurance":   ["hackernews", "github", "polymarket"],
    "bnpl_embedded":        ["reddit", "hackernews", "polymarket"],
    "open_insurance_api":   ["hackernews", "github", "arxiv"],
    "microinsurance":       ["hackernews"],
    "insurtech_funding":    ["techmeme", "stocktwits", "hackernews"],
    # 站点实际存在的其他子域名，补充源路由
    "ai_policy_cx":         ["reddit", "hackernews", "techmeme"],
    "ai_underwriting":      ["reddit", "hackernews", "github", "arxiv"],
    "decision_intelligence":["hackernews", "reddit", "arxiv", "polymarket"],
}

# 子域名（content/ 下的目录名）-> 主题键。用于生成管线按文章路由社区源。
# 站点真实子域名：ai-claims / ai-fraud-detection / ai-policy-cx / ai-underwriting /
#                  decision-intelligence / embedded-insurance
SUBDOMAIN_TO_THEME = {
    "ai-claims":            "ai_claims",
    "ai-fraud-detection":   "ai_fraud",
    "ai-policy-cx":         "ai_policy_cx",
    "ai-underwriting":      "ai_underwriting",
    "decision-intelligence": "decision_intelligence",
    "embedded-insurance":   "embedded_insurance",
}

# 半自动优先：先只给这两类主题自动注入社区区块（用户决策：先攻 ai_claims/ai_fraud）。
# 其余主题主题路由已就绪，后续把主题名加进这个列表即可全量铺开。
COMMUNITY_THEMES = ["ai_claims", "ai_fraud"]

# 生成管线默认不调社区 API（避免 CI / 自动 cron 乱花 ScrapeCreators 额度）。
# 需要注入时 export COMMUNITY_ENABLE=1 再跑生成/回填脚本。
COMMUNITY_ENABLE_ENV = "COMMUNITY_ENABLE"

# 仍不可达、拿到 key 后可并回的高价值源：
#   linkedin -> embedded_insurance / microinsurance / insurtech_funding（B2B 观点）
#   bluesky  -> 全主题补充（public.api.bsky.app 在本环境 403）
UNLOCKABLE_SOURCES = ["linkedin", "bluesky"]

# 默认采集窗口（天）；可按文章覆盖
DEFAULT_WINDOW_DAYS = 30

# 每篇文章最多引用条数（避免页面臃肿）
MAX_QUOTES_PER_ARTICLE = 5

# 相关性过滤关键词（命中任一才保留，降低无关噪音）
RELEVANCE_KEYWORDS = [
    "insurance", "insurer", "insurtech", "claim", "claims", "underwrit",
    "policy", "premium", "fraud", "adjuster", "embedded", "bnpl", "risk",
    "actuar", "broker", "reinsur", "policyholder", "coverage", "loss ratio",
    "parametric", "lemons", "lemonade", "root insurance", "embed",
]


def sources_for_theme(theme: str) -> list:
    """返回某子主题应查询的源列表（过滤掉未启用的）。"""
    return THEME_TO_SOURCES.get(theme, ["hackernews", "reddit", "dripstack"])


def is_relevant(text: str) -> bool:
    """保险主题相关性初筛（大小写不敏感）。"""
    t = (text or "").lower()
    return any(k in t for k in RELEVANCE_KEYWORDS)
