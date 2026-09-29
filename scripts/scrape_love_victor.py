#!/usr/bin/env python3
"""
Scraper for Love, Victor transcripts from Forever Dreaming
URL: https://transcripts.foreverdreaming.org/viewforum.php?f=1079
Bypasses Anubis Proof-of-Work (PoW) challenge and downloads all episodes.
"""

import os
import re
import sys
import time
import json
import hashlib
from urllib.parse import urljoin, quote
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://transcripts.foreverdreaming.org/"
FORUM_URL = "https://transcripts.foreverdreaming.org/viewforum.php?f=1079"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Love-Victor-Transcripts")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def solve_anubis_challenge(session: requests.Session, challenge_page_url: str, html_text: str) -> requests.Response:
    """Solve Anubis Proof-of-Work challenge and return the redirected page response."""
    m_chal = re.search(r'<script id="challenge" type="application/json">\s*(\{.*?\})\s*</script>', html_text, re.DOTALL)
    m_set = re.search(r'<script id="anubis_settings" type="application/json">\s*(\{.*?\})\s*</script>', html_text, re.DOTALL)
    if not m_chal or not m_set:
        raise ValueError("Could not find challenge data in page")

    c_data = json.loads(m_chal.group(1))
    s_data = json.loads(m_set.group(1))

    challenge = c_data["challenge"]
    difficulty = int(c_data["rules"]["difficulty"])
    timestamp = c_data["timestamp"]
    pass_route = s_data["routes"]["pass"]

    print(f"[*] Solving Anubis PoW challenge (difficulty={difficulty})...")
    target_prefix = "0" * difficulty
    t0 = time.time()
    nonce = 0
    while True:
        h = hashlib.sha256((challenge + str(nonce)).encode("utf-8")).hexdigest()
        if h.startswith(target_prefix):
            break
        nonce += 1
    elapsed_ms = int((time.time() - t0) * 1000)
    print(f"[*] Solved in {elapsed_ms}ms! Nonce: {nonce}")

    pass_url = urljoin(challenge_page_url, pass_route)
    pass_params = {
        "response": h,
        "nonce": nonce,
        "redir": FORUM_URL,
        "timestamp": timestamp,
        "elapsedTime": elapsed_ms,
    }
    resp = session.get(pass_url, params=pass_params)
    return resp


def get_session_and_forum_soup():
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"[*] Accessing forum: {FORUM_URL}")
    r = session.get(FORUM_URL)
    if "make_challenge" in r.text:
        print("[*] Anubis challenge triggered.")
        challenge_url = "https://transcripts.foreverdreaming.org/app.php/anubis/api/make_challenge?redir=" + quote(FORUM_URL, safe="")
        r_chal = session.get(challenge_url)
        r = solve_anubis_challenge(session, challenge_url, r_chal.text)

    soup = BeautifulSoup(r.text, "html.parser")
    return session, soup


def sanitize_filename(name: str) -> str:
    """Remove unsafe characters for filesystem."""
    # Replace illegal/annoying characters (?, *, :, /, \, etc.)
    name = re.sub(r'[*?"<>|/\\:]', '', name)
    return name.strip()


def parse_forum_topics(soup: BeautifulSoup):
    topics = []
    pattern = re.compile(r'^(\d{2})x(\d{2})\s*-\s*(.*)$')
    for a in soup.find_all("a", class_="topictitle"):
        raw_title = a.get_text(strip=True)
        href = a["href"]
        full_url = urljoin(FORUM_URL, href)
        m = pattern.match(raw_title)
        if m:
            season = int(m.group(1))
            episode = int(m.group(2))
            ep_title = m.group(3).strip()
            topics.append({
                "raw_title": raw_title,
                "season": season,
                "episode": episode,
                "title": ep_title,
                "url": full_url,
            })
        else:
            print(f"[-] Skipping non-episode topic: {raw_title}")

    # Sort topics by season and episode
    topics.sort(key=lambda x: (x["season"], x["episode"]))
    return topics


def scrape_topic_content(session: requests.Session, topic_info: dict):
    url = topic_info["url"]
    print(f"[*] Fetching S{topic_info['season']:02d}E{topic_info['episode']:02d}: {topic_info['title']} ({url})")
    
    # Retry logic
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20)
            if "make_challenge" in r.text:
                challenge_url = "https://transcripts.foreverdreaming.org/app.php/anubis/api/make_challenge?redir=" + quote(url, safe="")
                r_chal = session.get(challenge_url)
                r = solve_anubis_challenge(session, challenge_url, r_chal.text)

            if r.status_code != 200:
                print(f"  [!] HTTP {r.status_code}, retrying...")
                time.sleep(2)
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            
            # Post date
            time_tag = soup.find("time")
            post_date = time_tag.get_text(strip=True) if time_tag else "Unknown"

            content = soup.find("div", class_="content")
            if not content:
                print("  [!] Could not find div.content")
                return None

            # Remove ads and scripts
            for s in content.find_all(["script", "style", "noscript"]):
                s.decompose()
            for ad in content.find_all(class_=re.compile(r'\bads\b|adsbygoogle')):
                ad.decompose()

            # Convert br to \n
            for br in content.find_all("br"):
                br.replace_with("\n")

            text = content.get_text()
            # Normalize whitespace and excessive blank lines
            cleaned_text = re.sub(r'\r\n', '\n', text)
            cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()

            return {
                "post_date": post_date,
                "text": cleaned_text,
                "char_count": len(cleaned_text),
                "line_count": len(cleaned_text.splitlines()),
            }
        except Exception as e:
            print(f"  [!] Error on attempt {attempt + 1}: {e}")
            time.sleep(2)

    return None


def main():
    session, soup = get_session_and_forum_soup()
    topics = parse_forum_topics(soup)

    print(f"[*] Total episodes found: {len(topics)}")
    if len(topics) == 0:
        print("[!] No episode topics found! Aborting.")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = []

    for i, t in enumerate(topics, 1):
        season_dir = os.path.join(OUTPUT_DIR, f"Season {t['season']}")
        os.makedirs(season_dir, exist_ok=True)

        safe_title = sanitize_filename(t["title"])
        filename = f"S{t['season']:02d}E{t['episode']:02d} - {safe_title}.md"
        file_path = os.path.join(season_dir, filename)

        topic_data = scrape_topic_content(session, t)
        if not topic_data:
            print(f"[!] Failed to fetch content for S{t['season']:02d}E{t['episode']:02d}")
            continue

        md_content = f"""# Love, Victor - S{t['season']:02d}E{t['episode']:02d} - {t['title']}

- **Series**: Love, Victor
- **Season**: {t['season']}
- **Episode**: {t['episode']}
- **Title**: {t['title']}
- **Original URL**: {t['url']}
- **Post Date**: {topic_data['post_date']}
- **Characters**: {topic_data['char_count']}
- **Lines**: {topic_data['line_count']}

---

{topic_data['text']}
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"  [+] Saved to {os.path.relpath(file_path, OUTPUT_DIR)} ({topic_data['char_count']} chars, {topic_data['line_count']} lines)")

        results.append({
            **t,
            "filename": filename,
            "rel_path": f"Season {t['season']}/{filename}",
            "post_date": topic_data["post_date"],
            "char_count": topic_data["char_count"],
            "line_count": topic_data["line_count"],
        })

        # Polite delay
        time.sleep(0.6)

    # Generate README.md index
    readme_path = os.path.join(OUTPUT_DIR, "README.md")
    readme_lines = [
        "# Love, Victor Transcripts (剧本全集)",
        "",
        "> 美剧《Love, Victor》（爱你，维克托）全 3 季 28 集英文剧本/对白文本，爬取自 Forever Dreaming Transcripts (f=1079)。",
        "",
        f"- **总季数**: 3 季",
        f"- **总集数**: {len(results)} 集",
        f"- **总字数**: {sum(r['char_count'] for r in results):,} 字符",
        f"- **抓取来源**: [{FORUM_URL}]({FORUM_URL})",
        f"- **抓取时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 剧集目录",
        "",
    ]

    current_season = None
    for r in results:
        if r["season"] != current_season:
            current_season = r["season"]
            readme_lines.append(f"### Season {current_season}")
            readme_lines.append("")
            readme_lines.append("| 集数 | 标题 | 原始链接 | 字数 | 行数 | 本地文件 |")
            readme_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        # Encode path for markdown link
        link_target = quote(r['rel_path'])
        readme_lines.append(
            f"| S{r['season']:02d}E{r['episode']:02d} | {r['title']} | [Forever Dreaming]({r['url']}) | {r['char_count']:,} | {r['line_count']:,} | [{r['filename']}]({link_target}) |"
        )
        if results.index(r) == len(results) - 1 or results[results.index(r) + 1]["season"] != current_season:
            readme_lines.append("")

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(readme_lines))

    print(f"\n[✓] Finished! Index generated at {readme_path}")
    print(f"[✓] Successfully downloaded {len(results)} / {len(topics)} episodes.")


if __name__ == "__main__":
    main()
