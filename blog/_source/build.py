#!/usr/bin/env python3
"""サイトを組み立てる。

使い方:  python3 _source/build.py
config.json と posts/*.md を読み、blog/ 直下にHTMLを書き出す。
追加ライブラリは不要（Python 3 標準機能のみ）。

ブログ側はWordPressのブログテーマによくある形（2カラム＋サイドバー、
パンくず、目次、関連記事、前後の記事）で組む。
会社案内のページは1カラムのまま。
"""
import html
import json
import re
import shutil
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

E = html.escape


def iso_date(text):
    """2026.08.26 -> 2026-08-26（検索エンジンが読む形式）"""
    return text.strip().replace(".", "-")


# ---------------------------------------------------------------- Markdown
def inline(text):
    """**強調** と [文字](URL) だけを変換する。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def slugify(text, seen):
    """見出しから目次リンク用のidを作る。日本語はそのまま使えないので連番にする。"""
    base = "midashi"
    n = seen.get(base, 0) + 1
    seen[base] = n
    return f"{base}-{n}"


def render_markdown(body):
    """記事本文で使う記法だけに絞ったMarkdown変換。

    見出し(##/###)、段落、箇条書き(-)、番号付き(1.)、**強調**、リンク、
    :::point ラベル 〜 ::: （ポイント枠）、:::ad ラベル （広告枠）に対応する。
    戻り値は (本文HTML, 目次の見出しリスト)。
    """
    out, heads, seen = [], [], {}
    lines, i = body.split("\n"), 0
    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        if line.startswith(":::ad"):
            label = line[len(":::ad"):].strip()
            out.append(f'        <div class="affiliate-slot">［{E(label)}］</div>')
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
            out.append(f'          <div class="point-label">{E(label)}</div>')
            out.append(f'          <p style="margin:8px 0 0;">{inner}</p>')
            out.append("        </div>")
            continue

        if line.startswith("### "):
            text = line[4:].strip()
            hid = slugify(text, seen)
            heads.append((3, hid, text))
            out.append(f'        <h3 id="{hid}">{inline(text)}</h3>')
            i += 1
            continue

        if line.startswith("## "):
            text = line[3:].strip()
            hid = slugify(text, seen)
            heads.append((2, hid, text))
            out.append(f'        <h2 id="{hid}">{inline(text)}</h2>')
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

    return "\n".join(out), heads


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


# ---------------------------------------------------------------- 共通パーツ
def json_ld(data):
    """構造化データ（検索結果での見え方に効く）"""
    return ('  <script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False, indent=2)
            + "\n  </script>\n")


def breadcrumb_ld(trail, up=""):
    """パンくずを検索エンジンにも同じ形で伝える。"""
    site = CFG["siteUrl"]
    items = []
    for i, (href, label) in enumerate(trail, start=1):
        entry = {"@type": "ListItem", "position": i, "name": label}
        if href:
            entry["item"] = f"{site}/{href}"
        items.append(entry)
    return json_ld({"@context": "https://schema.org",
                    "@type": "BreadcrumbList",
                    "itemListElement": items})


def head(title, desc, page, img, og_type="website", up="", body_class="", extra_head=""):
    site = CFG["siteUrl"]
    cls = f' class="{body_class}"' if body_class else ""
    nav = "\n".join(f'      <li><a href="{up}{h}">{l}</a></li>' for h, l in NAV)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{E(title)}</title>
  <meta name="description" content="{E(desc)}">
  <!-- SNSシェア用。公開ドメインを変えたら config.json の siteUrl を直す -->
  <meta property="og:type" content="{og_type}">
  <meta property="og:title" content="{E(title)}">
  <meta property="og:description" content="{E(desc)}">
  <meta property="og:url" content="{site}/{page}">
  <meta property="og:image" content="{site}/{img}">
  <meta property="og:site_name" content="{E(CFG['company'])}">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <!-- 同じ内容が複数のURLで見えても、検索エンジンにはこれが正規だと伝える -->
  <link rel="canonical" href="{site}/{page}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{FONTS}" media="print" onload="this.media='all'">
  <noscript><link rel="stylesheet" href="{FONTS}"></noscript>
  <link rel="stylesheet" href="{up}css/style.css">
{extra_head}</head>
<body{cls}>

<header class="site-header">
  <div class="container">
    <div class="site-title"><a href="{up}index.html">{E(CFG['company'])}</a></div>
    <div class="site-desc">{E(CFG['tagline'])}</div>
  </div>
</header>

<nav class="global-nav">
  <div class="container">
    <ul>
{nav}
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
    <div class="copyright">&copy; {CFG['copyrightYear']} {E(CFG['company'])}</div>
  </div>
</footer>

</body>
</html>
"""


def breadcrumb(trail, up=""):
    """パンくずリスト。trail は [(リンク先 or None, 表示名), ...]。"""
    parts = []
    for href, label in trail:
        if href:
            parts.append(f'<li><a href="{up}{href}">{E(label)}</a></li>')
        else:
            parts.append(f'<li aria-current="page">{E(label)}</li>')
    return ('  <nav class="breadcrumb" aria-label="現在の位置">\n'
            '    <div class="container">\n      <ol>\n        '
            + "\n        ".join(parts)
            + "\n      </ol>\n    </div>\n  </nav>\n")


def cta(heading, lead, up=""):
    return f"""
  <section class="cta-band">
    <div class="container">
      <h2>{heading}</h2>
      <p>{lead}</p>
      <a class="btn btn-primary" href="{up}contact.html">お問い合わせフォームへ</a>
    </div>
  </section>
"""


def service_cards():
    out = []
    for s in CFG["services"]:
        li = "\n".join(f"          <li>{E(i)}</li>" for i in s["items"])
        out.append(f"""      <div class="service-card">
        <h3>{E(s['name'])}</h3>
        <p>{E(s['lead'])}</p>
        <ul>
{li}
        </ul>
      </div>""")
    return "\n".join(out)


# ---------------------------------------------------------------- ブログ用パーツ
def post_card(post, up=""):
    """記事一覧のカード（画像の上にカテゴリのラベルが乗る形）。"""
    tags = "".join(f'<span class="tag">{E(t)}</span>' for t in post["tags"])
    return f"""        <li class="post-card">
          <a href="{up}articles/{post['slug']}.html">
            <div class="post-card-thumb">
              <img src="{up}images/eyecatch-{post['slug']}.png"
                   alt="" width="1200" height="630" loading="lazy">
              <span class="cat-badge">{E(post['category'])}</span>
            </div>
            <div class="post-card-body">
              <div class="post-card-date">{post['date']}</div>
              <h3 class="post-card-title">{E(post['title'])}</h3>
              <p class="post-card-excerpt">{E(post['excerpt'])}</p>
              <div class="post-card-foot">{tags}<span class="more">続きを読む →</span></div>
            </div>
          </a>
        </li>"""


def popular_posts(posts):
    """人気記事の並び順。

    config.json の popular にファイル名を並べた順で出す。
    アクセス数を勝手に作ることはできないので、空のときは新しい順にする。
    """
    order = CFG.get("popular") or []
    by_slug = {p["slug"]: p for p in posts}
    picked = [by_slug[s] for s in order if s in by_slug]
    rest = [p for p in posts if p not in picked]
    return picked + rest


def sidebar(posts, up=""):
    a = CFG["author"]
    cats = {}
    for p in posts:
        cats[p["category"]] = cats.get(p["category"], 0) + 1
    cat_items = "\n".join(
        f'          <li><a href="{up}blog.html">{E(c)}</a><span class="count">{n}</span></li>'
        for c, n in sorted(cats.items(), key=lambda kv: -kv[1]))
    ranking = "\n".join(f"""            <li>
              <a href="{up}articles/{p['slug']}.html">
                <img src="{up}images/eyecatch-{p['slug']}.png" alt=""
                     width="1200" height="630" loading="lazy">
                <span>{E(p['title'])}</span>
              </a>
            </li>""" for p in popular_posts(posts)[:5])

    recent = "\n".join(f"""          <li>
            <a href="{up}articles/{p['slug']}.html">
              <img src="{up}images/eyecatch-{p['slug']}.png" alt=""
                   width="1200" height="630" loading="lazy">
              <span>
                <span class="recent-date">{p['date']}</span>
                {E(p['title'])}
              </span>
            </a>
          </li>""" for p in posts[:4])

    return f"""      <aside class="l-side">
        <section class="widget widget-profile">
          <h2 class="widget-title">このブログについて</h2>
          <div class="profile-avatar" aria-hidden="true">{E(a['name'][0])}</div>
          <p class="profile-name">{E(a['name'])}<span>{E(a['role'])}</span></p>
          <p class="profile-bio">{E(a['bio'])}</p>
          <a class="widget-link" href="{up}about.html">プロフィールを見る →</a>
        </section>

        <section class="widget">
          <h2 class="widget-title">カテゴリー</h2>
          <ul class="widget-cats">
{cat_items}
          </ul>
        </section>

        <section class="widget">
          <h2 class="widget-title">人気の記事</h2>
          <ol class="widget-rank">
{ranking}
          </ol>
        </section>

        <section class="widget">
          <h2 class="widget-title">最新の記事</h2>
          <ul class="widget-recent">
{recent}
          </ul>
        </section>

        <section class="widget widget-cta">
          <h2 class="widget-title">お仕事のご依頼</h2>
          <p>制作のご相談・お見積もりを承っています。</p>
          <a class="btn btn-primary btn-block" href="{up}contact.html">お問い合わせ</a>
        </section>
      </aside>"""


def toc(heads):
    """記事冒頭の目次。日本のWPブログでおなじみの開閉できる箱。"""
    if len(heads) < 3:
        return ""
    items = []
    for level, hid, text in heads:
        cls = ' class="toc-sub"' if level == 3 else ""
        items.append(f'            <li{cls}><a href="#{hid}">{E(text)}</a></li>')
    return ('        <details class="toc" open>\n'
            '          <summary>目次</summary>\n'
            '          <ol>\n' + "\n".join(items) + "\n          </ol>\n"
            "        </details>\n")


def related(posts, current, up=""):
    """同じカテゴリを優先して2本選ぶ。足りなければ新しい順で補う。"""
    same = [p for p in posts if p["slug"] != current["slug"]
            and p["category"] == current["category"]]
    others = [p for p in posts if p["slug"] != current["slug"] and p not in same]
    picked = (same + others)[:2]
    if not picked:
        return ""
    cards = "\n".join(post_card(p, up) for p in picked)
    return f"""
      <section class="related">
        <h2 class="block-title">あわせて読みたい</h2>
        <ul class="post-grid">
{cards}
        </ul>
      </section>
"""


def post_nav(posts, current, up=""):
    idx = next(i for i, p in enumerate(posts) if p["slug"] == current["slug"])
    newer = posts[idx - 1] if idx > 0 else None
    older = posts[idx + 1] if idx + 1 < len(posts) else None
    parts = []
    if newer:
        parts.append(f"""        <a class="post-nav-item is-prev" href="{up}articles/{newer['slug']}.html">
          <span class="post-nav-label">← 新しい記事</span>
          <span class="post-nav-title">{E(newer['title'])}</span>
        </a>""")
    if older:
        parts.append(f"""        <a class="post-nav-item is-next" href="{up}articles/{older['slug']}.html">
          <span class="post-nav-label">古い記事 →</span>
          <span class="post-nav-title">{E(older['title'])}</span>
        </a>""")
    if not parts:
        return ""
    return '      <nav class="post-nav">\n' + "\n".join(parts) + "\n      </nav>\n"


def author_box(up=""):
    a = CFG["author"]
    return f"""      <section class="author-box">
        <div class="author-avatar" aria-hidden="true">{E(a['name'][0])}</div>
        <div class="author-text">
          <p class="author-name">{E(a['name'])}<span>{E(a['role'])}</span></p>
          <p>{E(a['bio'])}</p>
          <a href="{up}about.html">プロフィールを見る →</a>
        </div>
      </section>
"""


# ---------------------------------------------------------------- 各ページ
def build_index(posts):
    hero = CFG["hero"]
    about = "\n".join(f"      <p>{p}</p>" for p in CFG["about"])
    latest = "\n".join(post_card(p) for p in posts[:2])
    s = head(f"{CFG['company']}｜{CFG['tagline']}",
             "AIを活用したコンテンツ制作・診断コンテンツ制作・SNS運用支援を行っています。"
             "企画から制作まで一貫してお引き受けします。",
             "index.html", "images/ogp-top.png",
             extra_head=json_ld({
                 "@context": "https://schema.org",
                 "@type": "WebSite",
                 "name": CFG["company"],
                 "description": CFG["tagline"],
                 "url": CFG["siteUrl"] + "/",
                 "inLanguage": "ja",
             }))
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
      <ul class="post-grid">
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
    flow = "\n".join(f"      <li><strong>{E(t)}</strong>：{E(d)}</li>" for t, d in CFG["flow"])
    s = head(f"事業内容｜{CFG['company']}",
             "AIを活用したコンテンツ制作、診断コンテンツ制作、SNS・動画運用支援、"
             "AI活用の教育・コミュニティ運営について紹介します。",
             "services.html", "images/ogp-top.png",
             extra_head=breadcrumb_ld([("index.html", "ホーム"), (None, "事業内容")]))
    s += breadcrumb([("index.html", "ホーム"), (None, "事業内容")])
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
        cell = E(value)
        if todo:
            cell += ("　" if cell else "") + f'<span class="todo">{E(todo)}</span>'
        rows.append(f"        <tr><th>{E(label)}</th><td>{cell}</td></tr>")
    rows.append('        <tr><th>連絡先</th><td><a href="contact.html">お問い合わせフォーム</a></td></tr>')
    values = "\n".join(f"    <p>{E(v)}</p>" for v in CFG["values"])
    s = head(f"会社概要｜{CFG['company']}",
             f"{CFG['company']}の会社概要と、事業に対する考え方をご紹介します。",
             "company.html", "images/ogp-top.png",
             extra_head=breadcrumb_ld([("index.html", "ホーム"), (None, "会社概要")]))
    s += breadcrumb([("index.html", "ホーム"), (None, "会社概要")])
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
    items = "\n".join(post_card(p) for p in posts)
    s = head(f"ブログ｜{CFG['company']}",
             "AI活用と副業の始め方について、実際にやってみたことを書いています。",
             "blog.html", "images/ogp-top.png", body_class="has-side",
             extra_head=breadcrumb_ld([("index.html", "ホーム"), (None, "ブログ")]))
    s += breadcrumb([("index.html", "ホーム"), (None, "ブログ")])
    s += f"""
<main>
  <div class="container">
    <div class="l-wrap">
      <div class="l-main">
        <h1 class="block-title">ブログ</h1>
        <p class="section-lead">{E(CFG['sidebarNote'])}</p>
        <ul class="post-grid">
{items}
        </ul>
      </div>
{sidebar(posts)}
    </div>
  </div>
</main>
"""
    (OUT / "blog.html").write_text(s + foot(), encoding="utf-8")


def build_articles(posts):
    (OUT / "articles").mkdir(exist_ok=True)
    for p in posts:
        body_html, heads = render_markdown(p["body"])
        # カテゴリと同じ名前のタグは重ねて出さない
        tags = "".join(f'<span class="tag">{E(t)}</span>'
                       for t in p["tags"] if t != p["category"])
        site = CFG["siteUrl"]
        page_url = f"articles/{p['slug']}.html"
        img_url = f"{site}/images/eyecatch-{p['slug']}.png"
        published = iso_date(p["date"])
        article_ld = json_ld({
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "mainEntityOfPage": {"@type": "WebPage", "@id": f"{site}/{page_url}"},
            "headline": p["title"],
            "description": p["description"],
            "image": [img_url],
            "datePublished": published,
            "dateModified": published,
            "articleSection": p["category"],
            "keywords": ", ".join(p["tags"]),
            "inLanguage": "ja",
            # 会社ではなく個人が書いているので Person にする
            "author": {"@type": "Person", "name": CFG["author"]["name"]},
            "publisher": {"@type": "Person", "name": CFG["author"]["name"]},
        })
        crumb_ld = breadcrumb_ld([("index.html", "ホーム"), ("blog.html", "ブログ"),
                                  (None, p["category"])])
        s = head(f"{p['title']}｜{CFG['company']}", p["description"],
                 page_url, f"images/eyecatch-{p['slug']}.png", "article",
                 up="../", body_class="has-side",
                 extra_head=article_ld + crumb_ld)
        s += breadcrumb([("index.html", "ホーム"), ("blog.html", "ブログ"),
                         (None, p["category"])], up="../")
        s += f"""
<main>
  <div class="container">
    <div class="l-wrap">
      <div class="l-main">
        <article class="post">
          <header class="article-header">
            <div class="article-cats"><span class="cat-badge is-plain">{E(p['category'])}</span>{tags}</div>
            <h1>{E(p['title'])}</h1>
            <div class="article-meta"><time datetime="{published}">{p['date']}</time></div>
          </header>

          <img class="eyecatch" src="../images/eyecatch-{p['slug']}.png"
               alt="{E(p['title'])}" width="1200" height="630">

          <div class="pr-note">※本記事にはアフィリエイト広告（PR）が含まれる場合があります。</div>

          <div class="article-body">
{toc(heads)}{body_html}
          </div>
        </article>

{author_box("../")}
{post_nav(posts, p, "../")}
{related(posts, p, "../")}
      </div>
{sidebar(posts, "../")}
    </div>
  </div>
</main>
"""
        (OUT / "articles" / f"{p['slug']}.html").write_text(s + foot("../"), encoding="utf-8")


def build_sitemap(posts):
    """検索エンジンにページの一覧を渡すファイル。"""
    site = CFG["siteUrl"]
    # 固定ページ（更新日は動かないので lastmod は付けない）
    urls = [(f"{site}/", "1.0", None),
            (f"{site}/blog.html", "0.9", None),
            (f"{site}/services.html", "0.7", None),
            (f"{site}/company.html", "0.7", None),
            (f"{site}/about.html", "0.6", None),
            (f"{site}/contact.html", "0.5", None),
            (f"{site}/privacy.html", "0.3", None)]
    for post in posts:
        urls.append((f"{site}/articles/{post['slug']}.html", "0.8", iso_date(post["date"])))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, priority, lastmod in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_robots():
    """クロールの許可とサイトマップの場所を伝えるファイル。"""
    (OUT / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {CFG['siteUrl']}/sitemap.xml\n",
        encoding="utf-8")


def build_404():
    """存在しないURLを開いたときのページ。"""
    s = head(f"ページが見つかりません｜{CFG['company']}",
             "お探しのページは見つかりませんでした。",
             "404.html", "images/ogp-top.png")
    s += """
<main>
  <div class="container page-body">
    <h1 class="section-title">ページが見つかりません</h1>
    <p>お探しのページは、移動または削除された可能性があります。</p>
    <p>お手数ですが、下のリンクからお探しください。</p>
    <p class="section-more"><a href="blog.html">ブログの記事一覧を見る →</a></p>
    <p class="section-more"><a href="index.html">トップページへ戻る →</a></p>
  </div>
</main>
"""
    (OUT / "404.html").write_text(s + foot(), encoding="utf-8")


# 公開するときに渡すのは dist/ だけ。_source/ を一緒に上げないためのもの。
PUBLISH_FILES = ["index.html", "services.html", "company.html", "blog.html",
                 "about.html", "contact.html", "privacy.html", "404.html",
                 "sitemap.xml", "robots.txt"]
PUBLISH_DIRS = ["css", "articles", "images"]


def build_dist():
    """公開用のファイルだけを dist/ にまとめる。

    blog/ の中には元データ（_source）も入っている。そのまま公開先へ
    上げると build.py や記事の下書きまで誰でも見られる状態になるので、
    公開して問題ないファイルだけをここに複製する。
    アップロードするときは、この dist フォルダごと渡せばよい。
    """
    dist = OUT / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()
    for name in PUBLISH_FILES:
        shutil.copy2(OUT / name, dist / name)
    for folder in PUBLISH_DIRS:
        src = OUT / folder
        if src.exists():
            shutil.copytree(src, dist / folder)
    return dist


def main():
    posts = load_posts()
    build_index(posts)
    build_services()
    build_company()
    build_blog(posts)
    build_articles(posts)
    build_sitemap(posts)
    build_robots()
    build_404()
    build_dist()
    print(f"生成しました：トップ・事業内容・会社概要・ブログ一覧 と 記事{len(posts)}本")
    print("　＋ sitemap.xml / robots.txt / 404.html（SEO用）")
    print("公開用のファイルは dist/ にまとめました（公開するときはこれを渡す）")
    print("※ 代表プロフィール(about.html)・お問い合わせ(contact.html)・"
          "プライバシーポリシー(privacy.html) は手書きのまま据え置きです")


if __name__ == "__main__":
    main()
