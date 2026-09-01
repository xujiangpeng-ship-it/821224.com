# -*- coding: utf-8 -*-
"""
community_sources.py — 统一「社区视角」抓取器
=============================================

读取 community_sources_config.py 的源池，按文章主题路由到相关源，
抓取真人讨论/评价，过滤垃圾与无关内容，排序后输出统一的 Quote schema，
再渲染成文章里的 "Community Perspectives" 区块（见 render_html）。

设计原则（与 config 一致）
--------------------------
- 只复用 last30days-skill 的"哪些源可用/怎么取"知识，自己写轻量 fetcher，
  不整体接管那个 agent CLI。
- 能直接 HTTP 抓的（HN / Polymarket / arXiv / GitHub / StockTwits / DripStack / Bluesky）
  用 requests + 代理；需 CLI/key 的（Trustpilot / Techmeme / Digg / Reddit OAuth）做
  best-effort，拿不到就静默返回空，不阻断文章生成。
- 所有 fetcher 都返回 List[Quote]；collect_for_article 负责路由、过滤、排序、截断。

运行需要：requests；代理走 http://127.0.0.1:10809（与生成器一致）。

调用示例（在生成管线里）：
    from community_sources import collect_for_article, render_html
    quotes = collect_for_article("ai_fraud", title="...", keyword="insurance fraud ai")
    if quotes:
        block_html = render_html(quotes, "ai_fraud")
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import requests

try:
    import community_sources_config as cfg
except Exception:  # 允许单独运行
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "community_sources_config",
        os.path.join(os.path.dirname(__file__), "community_sources_config.py"),
    )
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)

PROXY = os.environ.get("COMMUNITY_PROXY", "http://127.0.0.1:10809")
HTTP_PROXIES = {"http": PROXY, "https": PROXY}
REQ_TIMEOUT = 20

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


# ---------------------------------------------------------------------------
# 统一数据结构
# ---------------------------------------------------------------------------
@dataclass
class Quote:
    source: str          # hackernews / reddit / trustpilot / ...
    author: str          # 发布者/昵称
    text: str            # 引用正文（清理后）
    url: str             # 原文链接
    score: int           # 互动量（赞/点数），用于排序
    date: str            # ISO 日期或空
    topic: str = ""      # 所属子主题

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _request(url: str, params: Optional[dict] = None, headers: Optional[dict] = None,
             retries: int = 3):
    """带退避重试的 GET。HN Algolia 等端点会间歇性 500，单次失败就放弃会
    让整篇文章白白拿不到社区内容。"""
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=h,
                             proxies=HTTP_PROXIES, timeout=REQ_TIMEOUT)
            if r.status_code == 200:
                return r
            last = f"http {r.status_code}"
        except Exception as e:
            last = f"{type(e).__name__}"
        if attempt < retries - 1:
            time.sleep(2 ** attempt + 1)
    return None


def _get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[dict]:
    r = _request(url, params, headers)
    if r is None:
        return None
    try:
        return r.json()
    except Exception:
        return None  # 限流时可能返回 HTML


def _get_text(url: str, params: Optional[dict] = None) -> Optional[str]:
    r = _request(url, params)
    return r.text if r is not None else None


def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def _is_garbage(text: str) -> bool:
    """招聘广告 / 纯推广 / 引流话术过滤。

    招聘帖是 HN 搜索最大的噪声来源：形如 "Company | Multiple Engineering +
    Product Roles | Remote US | Full-time"，正文里也带 insurance 一词，
    会被关键词相关性误判为命中主题。
    """
    t = text.lower()
    spam = ["we're hiring", "now hiring", "dm me", "click the link",
            "join our", "sign up", "use my code", "promo code", "free trial",
            "subscribe to", "book a call", "🚀", "💰"]
    if any(k in t for k in spam):
        return True
    # HN "Who is hiring" 式招聘帖特征
    job = ["multiple engineering", "| remote", "full-time", "full time",
           "product roles", "engineering roles", "we are looking for",
           "open positions", "apply at", "job opening", "hiring for"]
    return any(k in t for k in job)


# ---------------------------------------------------------------------------
# 1) Hacker News（已验证可用，最强技术讨论源）
# ---------------------------------------------------------------------------
def fetch_hackernews(query: str, limit: int = 5) -> list[Quote]:
    url = "https://hn.algolia.com/api/v1/search"
    data = _get(url, params={"query": query, "tags": "comment", "hitsPerPage": 50})
    if not data:
        return []
    out = []
    for hit in data.get("hits", []):
        text = _clean_text(re.sub(r"<[^>]+>", "", hit.get("comment_text", "") or ""))
        if len(text) < 80:
            continue
        out.append(Quote(
            source="hackernews",
            author=hit.get("author", "anon") or "anon",
            text=text[:520],
            url=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            score=int(hit.get("points") or 0),
            date=hit.get("created_at", "")[:10],
        ))
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# 2) Reddit（OAuth；本沙箱数据中心 IP 常被 403，拿不到就返回空）
# ---------------------------------------------------------------------------
def _reddit_token() -> Optional[str]:
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    try:
        r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(cid, secret),
            headers={"User-Agent": UA},
            proxies=HTTP_PROXIES, timeout=REQ_TIMEOUT,
        )
        return r.json().get("access_token") if r.status_code == 200 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 2b) Reddit via ScrapeCreators（本环境唯一可行路径）
#     reddit.com 在本机被 403，且 OAuth app 创建需登录 reddit.com（用户同样打不开）。
#     ScrapeCreators 在自己的服务端抓取，注册与调用都不需要 reddit.com 访问权。
#     API key 走环境变量 SCRAPECREATORS_API_KEY —— 绝不写进代码或提交到仓库。
# ---------------------------------------------------------------------------
SC_BASE = "https://api.scrapecreators.com/v1"

# 从业者向板块优先；消费者板块作为补充（B2B 站以从业者口径为主）
PREFERRED_SUBS = {
    "insuranceadjusters", "insuranceprofessional", "insurtech",
    "actuary", "insurance", "claimsadjuster", "insurancesales",
    "riskmanagement", "underwriting",
}
# 与保险无关的板块，search 会大量召回，必须滤掉
BLOCKED_SUBS = {
    "stupidquestions", "ama", "scams", "accounting", "vacclaims",
    "nostupidquestions", "askreddit", "offmychest", "trueoffmychest",
    "legaladviceofftopic", "relationship_advice", "personalfinance",
}


def _sc_headers() -> Optional[dict]:
    key = os.environ.get("SCRAPECREATORS_API_KEY")
    if not key:
        return None
    return {"x-api-key": key, "Content-Type": "application/json"}


def _sub_ok(sub: str) -> bool:
    s = (sub or "").lower()
    return s in PREFERRED_SUBS and s not in BLOCKED_SUBS


def fetch_reddit_scrapecreators(query: str, limit: int = 5,
                                max_comment_posts: int = 2) -> list[Quote]:
    """搜索 Reddit 帖子并取高赞评论。

    实测要点：
      - /reddit/search 的 subreddit 参数无效（指定后仍返回全局结果），
        必须在客户端按 subreddit 过滤。
      - 每次搜索 1 credit，每次取评论 1 credit；max_comment_posts 控制成本。
    """
    h = _sc_headers()
    if not h:
        return []
    data = _get(f"{SC_BASE}/reddit/search",
                params={"query": query, "sort": "relevance", "period": "year"},
                headers=h)
    if not data:
        return []
    posts = [p for p in data.get("posts", []) if _sub_ok(p.get("subreddit"))]
    # 从业者板块优先，其次按互动量与评论数
    posts.sort(key=lambda p: (
        0 if p.get("subreddit", "").lower() in PREFERRED_SUBS else 1,
        -(int(p.get("score") or 0) + int(p.get("num_comments") or 0) * 3),
    ))

    out: list[Quote] = []
    for p in posts:
        body = _clean_text(p.get("selftext", "") or "")
        if len(body) >= 120:
            out.append(Quote(
                source="reddit",
                author=p.get("author", "anon") or "anon",
                text=body[:520],
                url="https://www.reddit.com" + (p.get("permalink") or ""),
                score=int(p.get("score") or 0),
                date=_ts_date(p.get("created_utc")),
                topic=f"r/{p.get('subreddit', '')}",
            ))
        if len(out) >= limit:
            break

    # 高价值帖再取评论（评论往往比主帖更有观点）
    for p in posts[:max_comment_posts]:
        if len(out) >= limit:
            break
        perm = p.get("permalink")
        if not perm:
            continue
        cd = _get(f"{SC_BASE}/reddit/post/comments",
                  params={"url": "https://www.reddit.com" + perm}, headers=h)
        if not cd:
            continue
        for c in cd.get("comments", []):
            if _is_garbage(c.get("body", "") or ""):
                continue
            author = c.get("author") or ""
            if author.lower() in ("automoderator", "deleted", "[deleted]"):
                continue
            text = _clean_text(c.get("body", "") or "")
            if len(text) < 80:
                continue
            out.append(Quote(
                source="reddit",
                author=author,
                text=text[:520],
                url="https://www.reddit.com" + (c.get("permalink") or perm),
                score=int(c.get("score") or 0),
                date=_ts_date(c.get("created_utc")),
                topic=f"r/{p.get('subreddit', '')}",
            ))
            if len(out) >= limit:
                break
    return out


def _ts_date(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def fetch_reddit(query: str, subs: Optional[list[str]] = None,
                 limit: int = 5) -> list[Quote]:
    """Reddit 统一入口：优先走 ScrapeCreators，无 key 时退回 OAuth（本环境不可用）。"""
    got = fetch_reddit_scrapecreators(query, limit)
    if got:
        return got
    token = _reddit_token()
    if not token:
        return []  # 无可用通道 -> 跳过，不阻断
    subs = subs or cfg.SOURCE_POOL["reddit"]["default_subs"]
    out = []
    for sub in subs:
        try:
            r = requests.get(
                f"https://oauth.reddit.com/r/{sub}/search",
                params={"q": query, "restrict_sr": 1, "sort": "top",
                        "t": "year", "limit": 25},
                headers={"Authorization": f"bearer {token}", "User-Agent": UA},
                proxies=HTTP_PROXIES, timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                continue
            for c in r.json().get("data", {}).get("children", []):
                d = c["data"]
                body = _clean_text(d.get("selftext", "") or d.get("body", ""))
                if len(body) < 80:
                    continue
                out.append(Quote(
                    source="reddit",
                    author=d.get("author", "anon"),
                    text=body[:520],
                    url=f"https://reddit.com{d.get('permalink', '')}",
                    score=int(d.get("score") or 0),
                    date=datetime.fromtimestamp(
                        d.get("created_utc", 0), tz=timezone.utc
                    ).strftime("%Y-%m-%d") if d.get("created_utc") else "",
                    topic=sub,
                ))
                if len(out) >= limit:
                    return out
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# 3) GitHub（gh CLI；技术类文章，开放保险 API）
# ---------------------------------------------------------------------------
def fetch_github(query: str, limit: int = 4) -> list[Quote]:
    try:
        import subprocess
        out = subprocess.run(
            ["gh", "search", "issues", query, "--limit", str(limit * 2),
             "--json", "title,url,body,author,comments,createdAt,repository"],
            capture_output=True, text=True, timeout=40,
        )
        if out.returncode != 0:
            return []
        items = json.loads(out.stdout or "[]")
    except Exception:
        return []
    res = []
    for it in items:
        body = _clean_text((it.get("body") or "")[:520])
        if len(body) < 60:
            continue
        res.append(Quote(
            source="github",
            author=(it.get("author") or {}).get("login", "dev") or "dev",
            text=body,
            url=it.get("url", ""),
            score=int(it.get("comments") or 0),
            date=(it.get("createdAt") or "")[:10],
            topic=it.get("repository", ""),
        ))
        if len(res) >= limit:
            break
    return res


# ---------------------------------------------------------------------------
# 4) Polymarket（Gamma API，预测市场，监管/政策 hook）
# ---------------------------------------------------------------------------
def fetch_polymarket(query: str, limit: int = 3) -> list[Quote]:
    data = _get("https://gamma-api.polymarket.com/markets",
                params={"limit": 20, "active": "true",
                        "title": query[:40]})
    if not data:
        return []
    res = []
    for m in data[:limit]:
        q = _clean_text(m.get("question", ""))
        if not q:
            continue
        res.append(Quote(
            source="polymarket",
            author="Polymarket",
            text=f"{q} (probability {m.get('probability', '?')})",
            url=f"https://polymarket.com/event/{m.get('slug', '')}",
            score=int(float(m.get("volume", 0) or 0)),
            date="",
        ))
    return res


# ---------------------------------------------------------------------------
# 5) arXiv（学术，反欺诈/LLM 保险应用）
# ---------------------------------------------------------------------------
def fetch_arxiv(query: str, limit: int = 3) -> list[Quote]:
    data = _get("http://export.arxiv.org/api/query",
                params={"search_query": f"all:{query}", "max_results": limit * 2,
                        "sortBy": "relevance"})
    if not data:
        return []
    # 极简 XML 解析
    entries = re.findall(r"<entry>(.*?)</entry>", data, re.DOTALL)
    res = []
    for e in entries[:limit]:
        title = _clean_text(re.search(r"<title>(.*?)</title>", e, re.DOTALL).group(1)) if re.search(r"<title>(.*?)</title>", e, re.DOTALL) else ""
        summary = _clean_text(re.search(r"<summary>(.*?)</summary>", e, re.DOTALL).group(1)) if re.search(r"<summary>(.*?)</summary>", e, re.DOTALL) else ""
        link = re.search(r'<id>(.*?)</id>', e)
        res.append(Quote(
            source="arxiv",
            author="arXiv",
            text=f"{title}. {summary[:400]}",
            url=link.group(1) if link else "",
            score=0, date="",
        ))
    return res


# ---------------------------------------------------------------------------
# 6) Techmeme（科技新闻 RSS，Insurtech 融资/动态，实测可用）
# ---------------------------------------------------------------------------
def fetch_techmeme(query: str, limit: int = 3) -> list[Quote]:
    xml = _get_text("https://techmeme.com/feed.xml")
    if not xml:
        return []
    items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    toks = [w.lower() for w in re.findall(r"\w+", query or "") if len(w) > 3]
    res = []
    for it in items:
        def tag(name):
            m = re.search(rf"<{name}>(.*?)</{name}>", it, re.DOTALL)
            return _clean_text(re.sub(r"<[^>]+>", "", m.group(1))) if m else ""
        title, desc = tag("title"), tag("description")
        blob = (title + " " + desc).lower()
        # 需命中查询词，或与保险主题相关
        if toks and not any(t in blob for t in toks):
            if not cfg.is_relevant(blob):
                continue
        link = tag("link")
        res.append(Quote(
            source="techmeme",
            author="Techmeme",
            text=(title + (". " + desc if desc else ""))[:420],
            url=link,
            score=0, date=tag("pubDate")[:16],
        ))
        if len(res) >= limit:
            break
    return res


# ---------------------------------------------------------------------------
# 7) StockTwits（仅股票/上市公司主题）
# ---------------------------------------------------------------------------
def fetch_stocktwits(symbol: str, limit: int = 3) -> list[Quote]:
    if not symbol:
        return []
    data = _get(f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json")
    if not data:
        return []
    res = []
    for m in data.get("messages", [])[:limit]:
        txt = _clean_text(m.get("body", ""))
        if len(txt) < 40:
            continue
        res.append(Quote(
            source="stocktwits",
            author=m.get("user", {}).get("username", "trader"),
            text=txt[:360],
            url=f"https://stocktwits.com/message/{m.get('id')}",
            score=int(m.get("likes", {}).get("total", 0) or 0),
            date=(m.get("created_at", "") or "")[:10],
        ))
    return res


# ---------------------------------------------------------------------------
# 路由表：源名 -> fetcher
# ---------------------------------------------------------------------------
FETCHERS = {
    "hackernews": lambda q, lim: fetch_hackernews(q, lim),
    "reddit": lambda q, lim: fetch_reddit(q, cfg.SOURCE_POOL["reddit"]["default_subs"], lim),
    "github": lambda q, lim: fetch_github(q, lim),
    "polymarket": lambda q, lim: fetch_polymarket(q, lim),
    "arxiv": lambda q, lim: fetch_arxiv(q, lim),
    "techmeme": lambda q, lim: fetch_techmeme(q, lim),
    "stocktwits": lambda q, lim: fetch_stocktwits("", lim),  # 需 ticker，外部传
}


def _query_candidates(title: str, keyword: str) -> list[str]:
    """生成检索词候选，由具体到宽泛。

    HN Algolia 对不同长度的查询响应不一致（实测 "insurance" 直接 500，
    而 "fraud detection insurance" 正常 200 且返回 218 条），所以拿不到结果时
    要能退到更短的查询，而不是直接放弃。
    """
    q = keyword or title
    q = re.sub(r"[^a-zA-Z0-9 ]", " ", q).strip()
    toks = [w for w in q.split() if len(w) > 2]
    cands = []
    for n in (4, 3, 2):
        if len(toks) >= n:
            cands.append(" ".join(toks[:n]))
    if toks:
        cands.append(toks[0])
    out, seen = [], set()
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out or ["insurance"]


def collect_for_article(theme: str, title: str, keyword: str = "",
                        window_days: int = None) -> list[Quote]:
    """按主题路由抓取 -> 相关性+垃圾过滤 -> 排序 -> 截断。

    返回统一 Quote 列表（空列表表示本次没采到可用真人内容）。
    """
    sources = cfg.sources_for_theme(theme)
    wanted = cfg.MAX_QUOTES_PER_ARTICLE
    pool: list[Quote] = []

    for src in sources:
        fn = FETCHERS.get(src)
        if not fn:
            continue
        got: list[Quote] = []
        for query in _query_candidates(title, keyword):
            try:
                got = fn(query, max(3, wanted))
            except Exception:
                got = []
            if got:
                break
        for q in got:
            q.topic = theme
            if _is_garbage(q.text):
                continue
            if not cfg.is_relevant(q.text) and not cfg.is_relevant(q.author):
                continue
            pool.append(q)
        # 源按优先级排列（见 THEME_TO_SOURCES）。Reddit 对保险垂直领域的质量远高于
        # HN（实测 HN 会补进 "messaging app" 之类无关内容），所以靠前的源一旦凑够
        # 就不再调用后面的源 —— 既保证质量，也省 ScrapeCreators 额度。
        if len(pool) >= wanted:
            break

    # 去重（同 url）
    seen, uniq = set(), []
    for q in pool:
        if q.url in seen:
            continue
        seen.add(q.url)
        uniq.append(q)

    window = window_days or cfg.DEFAULT_WINDOW_DAYS
    cutoff = datetime.now(timezone.utc).timestamp() - window * 86400
    recent, older = [], []
    for q in uniq:
        try:
            ts = datetime.fromisoformat(q.date).timestamp() if q.date else 0
        except Exception:
            ts = 0
        (recent if ts and ts >= cutoff else older).append(q)

    # 优先近期；近期不足 wanted 条时，用旧内容补足（保证有东西可展示）
    recent.sort(key=lambda q: (q.score, q.date), reverse=True)
    older.sort(key=lambda q: (q.score, q.date), reverse=True)
    return (recent + older)[:wanted]


# ---------------------------------------------------------------------------
# 渲染成文章区块
# ---------------------------------------------------------------------------
def render_html(quotes: list[Quote], theme: str) -> str:
    if not quotes:
        return ""
    items = []
    for q in quotes:
        src_label = {
            "hackernews": "Hacker News", "reddit": "Reddit",
            "github": "GitHub", "polymarket": "Polymarket",
            "arxiv": "arXiv", "techmeme": "Techmeme",
            "stocktwits": "StockTwits", "trustpilot": "Trustpilot",
        }.get(q.source, q.source)
        items.append(
            f'        <li>\n'
            f'          <blockquote>{_clean_text(q.text)}</blockquote>\n'
            f'          <cite>— {_clean_text(q.author)} on {src_label}'
            + (f' · {q.date}' if q.date else '')
            + (f' <a href="{q.url}" rel="nofollow noopener" target="_blank">source</a>'
               if q.url else '')
            + '</cite>\n'
            f'        </li>'
        )
    # 标题不写成 "What practitioners are saying"：Reddit 高赞帖年份可能较久，
    # 那样措辞会误导读者以为都是当下讨论。日期照实展示，措辞保持中性。
    return (
        '<section class="community-perspectives" aria-label="Community perspectives">\n'
        '  <h2>Community perspectives</h2>\n'
        '  <p class="community-note">Selected real discussions from insurance '
        'practitioners, adjusters and policyholders on public forums. Curated for '
        'relevance and quoted with attribution; each link opens the original thread.</p>\n'
        '  <ul class="community-list">\n'
        + "\n".join(items) + "\n"
        '  </ul>\n'
        '</section>'
    )


if __name__ == "__main__":
    # 自测：抓 ai_fraud 主题
    test = collect_for_article("ai_fraud",
                               "What if healthcare insurance fraud detection missed 40%",
                               "insurance fraud ai")
    print(f"quotes collected: {len(test)}")
    for q in test:
        print(f"  [{q.source}] {q.author}: {q.text[:90]}...")
    if test:
        print("\n--- HTML ---\n")
        print(render_html(test, "ai_fraud"))


# ---------------------------------------------------------------------------
# 缓存 + 生成管线便捷入口
# ---------------------------------------------------------------------------
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".community_cache")


def _cache_path(theme: str, slug: str) -> str:
    d = os.path.join(CACHE_DIR, theme)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{slug}.json")


def _load_cache(theme: str, slug: str) -> Optional[list]:
    p = _cache_path(theme, slug)
    if not os.path.exists(p):
        return None
    try:
        data = json.load(open(p, encoding="utf-8"))
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            return data
    except Exception:
        pass
    return None


def _save_cache(theme: str, slug: str, quotes: list) -> None:
    try:
        os.makedirs(os.path.join(CACHE_DIR, theme), exist_ok=True)
        json.dump([q.to_dict() for q in quotes], open(_cache_path(theme, slug), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception:
        pass


def build_community_section(subdomain: str, title: str, slug: str,
                            keyword: str = "") -> str:
    """生成管线便捷入口：按子域名路由 -> 抓社区 -> 渲染区块 HTML。

    返回空字符串表示本次不注入（主题不在允许列表 / 未启用 / 没采到内容）。
    结果按 (theme, slug) 缓存到 .community_cache/，重复渲染复用、不重复消耗额度。
    """
    theme = cfg.SUBDOMAIN_TO_THEME.get(subdomain)
    if not theme:
        return ""
    # 半自动：只给允许列表里的主题注入
    if theme not in cfg.COMMUNITY_THEMES:
        return ""
    if os.environ.get(cfg.COMMUNITY_ENABLE_ENV) != "1":
        return ""  # 默认不调 API，避免自动 cron 乱花额度
    cache = _load_cache(theme, slug)
    if cache is not None:
        quotes = [Quote(**d) for d in cache]
    else:
        quotes = collect_for_article(theme, title, keyword)
        _save_cache(theme, slug, quotes)
    if not quotes:
        return ""
    return render_html(quotes, theme)

