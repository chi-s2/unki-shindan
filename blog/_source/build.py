#!/usr/bin/env python3
"""サイトを組み立てる。

使い方:  python3 _source/build.py
config.json と posts/*.md を読み、blog/ 直下にHTMLを書き出す。
追加ライブラリは不要（Python 3 標準機能のみ）。
"""
import html
import json
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent
CFG = json.loads((SRC / "config.json").read_text(encoding="utf-8"))

NAV = [("index.html", "ホーム"), ("services.html", "事業内容"),
       ("company.html", "会社概要"), ("blog.html", "ブログ"),
       ("contact.html", "お問い合わせ")]
FOOTER_NAV = [("company.html", "会社概要"), ("about.html", "代表プロフィール"),
              ("contact.html", "お問い合わせ"), ("privacy.html", "プライバシーポリシー")]

FONTS = ("https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700"
         "&family=Zen+Old+Mincho:wght@400;700&display=swap")


# ---------------------------------------------------------------- Markdown
def inline(text):
    """**強調** と [文字](URL) だけを変換する。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  r'<a href="\2">\1</a>', text)
    return text


def render_markdown(body):
    """記事本文で使う記法だけに絞ったMarkdown変換。

    見出し(##/###)、段落、箇条書き(-)、番号付き(1.)、**強調**、リンク、
    :::point ラベル 〜 ::: （ポイント枠）、:::ad ラベル （広告枠）に対応する。
    """
    out, lines, i = [], body.split("\n"), 0
    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        if line.startswith(":::ad"):
            label = line[len(":::ad"):].strip()
            out.append(f'        <div class="affiliate-slot">［{html.escape(label)}］</div>')
            i += 1
            continue

        if line.startswith(":::point"):
            label = line[len(":::point"):].strip()
            i += 1
            buf = []
            while i < len(lines) and lines[i].strip() != ":::":
                buf.append(lines[i].rstrip())
                i += 1
            i += 1  # 閉じの ::: を飛ばす
            inner = inline(" ".join(b for b in buf if b.strip()))
            out.append('        <div class="point-box">')
            out.append(f'          <div class="point-label">{html.escape(label)}</div>')
            out.append(f'          <p style="margin:8px 0 0;">{inner}</p>')
            out.append("        </div>")
            continue

        if line.startswith("### "):
            out.append(f"        <h3>{inline(line[4:].strip())}</h3>")
            i += 1
            continue

        if line.startswith("## "):
            out.append(f"        <h2>{inline(line[3:].strip())}</h2>")
            i += 1
            continue

        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(inline(lines[i][2:].strip()))
                i += 1
            out.append("        <ul>")
            out.extend(f"          <li>{it}</li>" for it in items)
            out.append("        </ul>")
            continue

        if re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                items.append(inline(re.sub(r"^\d+\. ", "", lines[i]).strip()))
                i += 1
            out.append("        <ol>")
            out.extend(f"          <li>{it}</li>" for it in items)
            out.append("        </ol>")
            continue

        out.append(f"        <p>{inline(line.strip())}</p>")
        i += 1

    return "\n".join(out)


def load_posts():
    posts = []
    for path in sorted((SRC / "posts").glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        front, body = raw.split("\n---\n", 1)
        meta = {}
        for ln in front.strip().split("\n"):
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
        meta["slug"] = path.stem
        meta["body"] = body
        meta["tags"] = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
        meta["excerpt"] = meta.get("description", "")
        posts.append(meta)
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    return posts


# ---------------------------------------------------------------- レイアウト
def head(title, desc, page, img, og_type="website", up=""):
    site = CFG["siteUrl"]
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(desc)}">
  <!-- SNSシェア用。公開ドメインを変えたら config.json の siteUrl を直す -->
  <meta property="og:type" content="{og_type}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:url" content="{site}/{page}">
  <meta property="og:image" content="{site}/{img}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{FONTS}" media="print" onload="this.media='all'">
  <noscript><link rel="stylesheet" href="{FONTS}"></noscript>
  <link rel="stylesheet" href="{up}css/style.css">
</head>
<body>

<header class="site-header">
  <div class="container">
    <div class="site-title"><a href="{up}index.html">{html.escape(CFG['company'])}</a></div>
    <div class="site-desc">{html.escape(CFG['tagline'])}</div>
  </div>
</header>

<nav class="global-nav">
  <div class="container">
    <ul>
""" + "\n".join(f'      <li><a href="{up}{h}">{l}</a></li>' for h, l in NAV) + """
    </ul>
  </div>
</nav>
"""


def foot(up=""):
    items = "\n".join(f'      <li><a href="{up}{h}">{l}</a></li>' for h, l in FOOTER_NAV)
    return f"""
<footer class="site-footer">
  <div class="container">
    <ul class="footer-nav">
{items}
    </ul>
    <div class="copyright">&copy; {CFG['copyrightYear']} {html.escape(CFG['company'])}</div>
  </div>
</footer>

</body>
</html>
"""


def cta(heading, lead):
    return f"""
  <section class="cta-band">
    <div class="container">
      <h2>{heading}</h2>
      <p>{lead}</p>
      <a class="btn btn-primary" href="contact.html">お問い合わせフォームへ</a>
    </div>
  </section>
"""


def service_cards():
    out = []
    for s in CFG["services"]:
        li = "\n".join(f"          <li>{html.escape(i)}</li>" for i in s["items"])
        out.append(f"""      <div class="service-card">
        <h3>{html.escape(s['name'])}</h3>
        <p>{html.escape(s['lead'])}</p>
        <ul>
{li}
        </ul>
      </div>""")
    return "\n".join(out)


def card(post, up=""):
    tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in post["tags"])
    return f"""        <li class="article-card">
          <a href="{up}articles/{post['slug']}.html">
            <img class="card-thumb" src="{up}images/eyecatch-{post['slug']}.png"
                 alt="" width="1200" height="630" loading="lazy">
            <div class="card-body">
              <div class="card-title">{html.escape(post['title'])}</div>
              <div class="card-excerpt">{html.escape(post['excerpt'])}</div>
              <div class="card-meta">{tags}{post['date']}</div>
            </div>
          </a>
        </li>"""


# ---------------------------------------------------------------- 各ページ
def build_index(posts):
    hero = CFG["hero"]
    about = "\n".join(f"      <p>{p}</p>" for p in CFG["about"])
    latest = "\n".join(card(p) for p in posts[:2])
    s = head(f"{CFG['company']}｜{CFG['tagline']}",
             "AIを活用したコンテンツ制作・診断コンテンツ制作・SNS運用支援を行っています。"
             "企画から制作まで一貫してお引き受けします。",
             "index.html", "images/ogp-top.png")
    s += f"""
<section class="hero">
  <div class="container">
    <div class="hero-eyebrow">{hero['eyebrow']}</div>
    <h1 class="hero-title">{hero['title']}</h1>
    <p class="hero-lead">{hero['lead']}</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="contact.html">お問い合わせ</a>
      <a class="btn btn-ghost" href="services.html">事業内容を見る</a>
    </div>
  </div>
</section>

<main>
  <div class="container">
    <section class="section">
      <h2 class="section-title">事業内容</h2>
      <p class="section-lead">AIを使った制作と、その使い方を伝えることの両方をしています。</p>
      <div class="service-grid">
{service_cards()}
      </div>
      <p class="section-more"><a href="services.html">事業内容をくわしく見る →</a></p>
    </section>

    <section class="section">
      <h2 class="section-title">私たちについて</h2>
{about}
      <p class="section-more"><a href="company.html">会社概要を見る →</a></p>
    </section>

    <section class="section">
      <h2 class="section-title">ブログ</h2>
      <p class="section-lead">AI活用や副業の始め方について、実際にやってみたことを書いています。</p>
      <ul class="article-list">
{latest}
      </ul>
      <p class="section-more"><a href="blog.html">記事をすべて見る →</a></p>
    </section>
  </div>
{cta("ご相談・お見積もりはお気軽に", "「こういうことはできますか？」という段階のご相談も歓迎です。")}
</main>
"""
    (OUT / "index.html").write_text(s + foot(), encoding="utf-8")


def build_services():
    flow = "\n".join(
        f"      <li><strong>{html.escape(t)}</strong>：{html.escape(d)}</li>"
        for t, d in CFG["flow"])
    s = head(f"事業内容｜{CFG['company']}",
             "AIを活用したコンテンツ制作、診断コンテンツ制作、SNS・動画運用支援、"
             "AI活用の教育・コミュニティ運営について紹介します。",
             "services.html", "images/ogp-top.png")
    s += f"""
<main>
  <div class="container page-body">
    <h1 class="section-title">事業内容</h1>
    <p class="section-lead">AIを使った制作と、その使い方を伝えることの両方をしています。
      いずれも自分たちで実践し、成果が出た進め方をそのままサービスにしています。</p>

    <div class="service-grid">
{service_cards()}
    </div>

    <h2>ご依頼から納品までの流れ</h2>
    <ol class="flow">
{flow}
    </ol>
  </div>
{cta("まずはご相談ください", "できること・できないことを正直にお伝えします。")}
</main>
"""
    (OUT / "services.html").write_text(s + foot(), encoding="utf-8")


def build_company():
    rows = []
    for label, value, todo in CFG["profile"]:
        cell = html.escape(value)
        if todo:
            cell += ('　' if cell else '') + f'<span class="todo">{html.escape(todo)}</span>'
        rows.append(f"        <tr><th>{html.escape(label)}</th><td>{cell}</td></tr>")
    rows.append('        <tr><th>連絡先</th><td><a href="contact.html">お問い合わせフォーム</a></td></tr>')
    values = "\n".join(f"    <p>{html.escape(v)}</p>" for v in CFG["values"])
    s = head(f"会社概要｜{CFG['company']}",
             f"{CFG['company']}の会社概要と、事業に対する考え方をご紹介します。",
             "company.html", "images/ogp-top.png")
    s += f"""
<main>
  <div class="container page-body">
    <h1 class="section-title">会社概要</h1>

    <table class="info-table">
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>

    <h2>大事にしていること</h2>
{values}

    <h2>代表について</h2>
    <p>代表のプロフィールは<a href="about.html">代表プロフィール</a>のページに掲載しています。</p>
  </div>
{cta("お仕事のご依頼・ご相談", "お問い合わせフォームよりご連絡ください。")}
</main>
"""
    (OUT / "company.html").write_text(s + foot(), encoding="utf-8")


def build_blog(posts):
    items = "\n".join(card(p) for p in posts)
    s = head(f"ブログ｜{CFG['company']}",
             "AI活用と副業の始め方について、実際にやってみたことを書いています。",
             "blog.html", "images/ogp-top.png")
    s += f"""
<main>
  <div class="container">
    <h1 class="section-title">ブログ</h1>
    <p class="section-lead">AI活用や副業の始め方について、実際にやってみたことを書いています。</p>
    <ul class="article-list">
{items}
    </ul>
  </div>
</main>
"""
    (OUT / "blog.html").write_text(s + foot(), encoding="utf-8")


def build_articles(posts):
    (OUT / "articles").mkdir(exist_ok=True)
    for p in posts:
        s = head(f"{p['title']}｜{CFG['company']}", p["description"],
                 f"articles/{p['slug']}.html",
                 f"images/eyecatch-{p['slug']}.png", "article", up="../")
        s += f"""
<main>
  <div class="container">
    <div class="pr-note">※本記事にはアフィリエイト広告（PR）が含まれる場合があります。</div>

    <article>
      <img class="eyecatch" src="../images/eyecatch-{p['slug']}.png"
           alt="" width="1200" height="630">
      <header class="article-header">
        <h1>{html.escape(p['title'])}</h1>
        <div class="article-meta">公開日：{p['date']}　カテゴリ：{html.escape(p['category'])}</div>
      </header>

      <div class="article-body">
{render_markdown(p['body'])}
      </div>
    </article>
  </div>
</main>
"""
        (OUT / "articles" / f"{p['slug']}.html").write_text(s + foot("../"), encoding="utf-8")


def main():
    posts = load_posts()
    build_index(posts)
    build_services()
    build_company()
    build_blog(posts)
    build_articles(posts)
    print(f"生成しました：トップ・事業内容・会社概要・ブログ一覧 と 記事{len(posts)}本")
    print("※ 代表プロフィール(about.html)・お問い合わせ(contact.html)・"
          "プライバシーポリシー(privacy.html) は手書きのまま据え置きです")


if __name__ == "__main__":
    main()
