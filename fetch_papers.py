# coding: utf-8
"""
每日材料化工前沿论文抓取 + DeepSeek AI 中文总结
数据源：arXiv API（免费、开放、无需注册）
"""
import os
import datetime
import requests

# ========== 可调配置 ==========
# arXiv 分类：材料科学、软物质、化学物理、应用物理
CATEGORIES = [
    "cond-mat.mtrl-sci",   # 材料科学
    "cond-mat.soft",       # 软物质
    "physics.chem-ph",     # 化学物理
    "physics.app-ph",      # 应用物理
]
MAX_PAPERS = 15            # 每天抓多少篇
# ==============================

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


def fetch_arxiv_papers():
    """从 arXiv API 拉取最新论文（Atom XML 格式）"""
    cat_query = "+OR+".join([f"cat:{c}" for c in CATEGORIES])
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query={cat_query}"
        "&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={MAX_PAPERS}"
    )
    print(f"[1/4] 请求 arXiv: {url[:100]}...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    import feedparser
    feed = feedparser.parse(resp.text)

    papers = []
    for entry in feed.entries:
        papers.append({
            "title": entry.title.replace("\n", " ").strip(),
            "authors": ", ".join(a.name for a in getattr(entry, "authors", [])),
            "summary": entry.summary.replace("\n", " ").strip(),
            "link": entry.link,
            "published": entry.published[:10],
        })
    print(f"    抓到 {len(papers)} 篇论文")
    return papers


def ai_summarize(title, abstract, api_key):
    """用 DeepSeek 把英文摘要总结成 1-2 句中文"""
    if not api_key:
        return "（未配置 DEEPSEEK_API_KEY，跳过 AI 总结）"

    prompt = (
        "你是材料化工领域科研助手。把下面这篇论文摘要用1-2句中文概括："
        "研究了什么问题、用了什么方法、主要结论是什么。不超过80字。\n\n"
        f"标题：{title}\n摘要：{abstract}"
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    try:
        r = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"（AI 总结失败：{e}）"


def build_markdown(papers, api_key):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    lines = [f"# 材料化工每日前沿 · {today}\n"]
    lines.append(f"> 今日抓取 {len(papers)} 篇最新论文（来源 arXiv，AI 总结由 DeepSeek 生成）\n")

    for i, p in enumerate(papers, 1):
        print(f"[2/4] AI 总结第 {i}/{len(papers)} 篇：{p['title'][:40]}...")
        summary_cn = ai_summarize(p["title"], p["summary"], api_key)

        lines.append(f"\n## {i}. {p['title']}")
        lines.append(f"- **作者**：{p['authors']}")
        lines.append(f"- **发布**：{p['published']}")
        lines.append(f"- **AI 一句话总结**：{summary_cn}")
        lines.append(f"- **论文链接**：{p['link']}")
        lines.append(f"- **英文摘要（节选）**：{p['summary'][:400]}...\n")

    return "\n".join(lines), f"{today}.md"


def git_commit_push(filename):
    os.system('git config user.name "github-actions[bot]"')
    os.system('git config user.email "github-actions[bot]@users.noreply.github.com"')
    os.system(f'git add {filename}')
    os.system(f'git commit -m "daily digest {filename}" || echo "no changes"')
    os.system('git push')


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("[警告] 未检测到 DEEPSEEK_API_KEY 环境变量，AI 总结将跳过")

    papers = fetch_arxiv_papers()
    if not papers:
        print("[错误] 没抓到论文，退出")
        return

    content, filename = build_markdown(papers, api_key)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[3/4] 报告已生成：{filename}")

    if os.environ.get("GITHUB_ACTIONS"):
        print("[4/4] 在 GitHub Actions 环境中，自动 push...")
        git_commit_push(filename)
    else:
        print("[4/4] 本地运行，不 push。查看文件：" + filename)


if __name__ == "__main__":
    main()
