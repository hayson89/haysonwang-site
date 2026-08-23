# -*- coding: utf-8 -*-
"""
publish.py — Obsidian -> Quartz content 的 MD->HTML 发布脚本

用法:
  python publish.py            # 扫描 VAULT 中 publish:true 的笔记并生成 HTML 到 CONTENT
  python publish.py --dry      # 只打印将要发布的笔记，不写文件

笔记需在 frontmatter 里加:
  publish: true
  section: Nail_Disorders | Clinical_Practice | Medical_Education | Medical_Research
  slug: my-article-slug        # 可选，默认按文件名生成
  title / date / created       # 可选，缺省时自动推断
"""
import os, re, shutil, sys, datetime

VAULT = "E:/ObsidianVault"
CONTENT = "E:/Website/quartz/content"
TEMPLATE = "E:/Website/quartz/publish_template.html"

# 源路径 -> 真实栏目（小写英文 slug，匹配线上仓库结构）
PATH_SECTION = {
    "02_甲沟炎": "nail-disease",
    "06_Teaching": "clinical",
    "04_Clinical_cases": "clinical",
    "07_Science_Communication": "education",
    "Clippings": "education",
    "05_Research": "research",
    "01_Lisfranc injury": "research",
}
# 兼容用户写 CamelCase 旧名
CAMEL_TO_LOWER = {
    "Nail_Disorders": "nail-disease",
    "Clinical_Practice": "clinical",
    "Medical_Education": "education",
    "Medical_Research": "research",
}
# 栏目中文显示名
SECTION_LABEL = {
    "nail-disease": "甲病专题",
    "clinical": "临床实践",
    "education": "健康科普",
    "research": "医学研究",
}
KNOWN_SECTIONS = set(SECTION_LABEL)

IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp")

import markdown
MD = markdown.Markdown(extensions=["fenced_code", "tables", "toc", "sane_lists"])


def split_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def sanitize_slug(name):
    stem = os.path.splitext(name)[0]
    s = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return s or "article"


def section_for(src_rel):
    for key, sec in PATH_SECTION.items():
        if key in src_rel.replace("\\", "/"):
            return sec
    return None


def preprocess(body, src_dir, published_map):
    """处理 Obsidian 语法，返回 (md_text, needed_images[basename])"""
    needed = []
    # 1) 图片嵌入 ![[img]] -> ![img](images/img)
    def emb(m):
        name = m.group(1).split("|")[0].strip()
        if not name.lower().endswith(IMG_EXT):
            return m.group(0)
        needed.append(os.path.basename(name))
        return "![%s](images/%s)" % (os.path.basename(name), _enc(os.path.basename(name)))
    body = re.sub(r"!\[\[([^\]]+)\]\]", emb, body)

    # 2) 标准图片 ![](path) -> 收集并改写
    def img(m):
        alt, path = m.group(1), m.group(2).split("|")[0].strip()
        if path.startswith("http") or path.startswith("data:"):
            return m.group(0)
        base = os.path.basename(path.replace("\\", "/"))
        needed.append(base)
        return "![%s](images/%s)" % (alt, _enc(base))
    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img, body)

    # 3) wikilink [[Target|alias]] -> 链接(若已发布) 否则纯文本
    def link(m):
        inner = m.group(1)
        if "|" in inner:
            target, alias = inner.split("|", 1)
        else:
            target, alias = inner, inner
        key = target.strip().lower()
        if key in published_map:
            return '<a href="%s.html">%s</a>' % (published_map[key], alias.strip())
        return alias.strip()
    body = re.sub(r"\[\[([^\]]+)\]\]", link, body)

    # 4) callout > [!type] Title \n > body...
    body = _callouts(body)
    return body, needed


def _enc(name):
    return name.replace(" ", "%20")


def _callouts(text):
    lines = text.splitlines()
    out = []
    i = 0
    pat = re.compile(r"^>\s*\[!(\w+)\]\s*(.*)$")
    cont = re.compile(r"^>\s?(.*)$")
    while i < len(lines):
        m = pat.match(lines[i])
        if m:
            ctype, ctitle = m.group(1).lower(), m.group(2).strip()
            i += 1
            buf = []
            while i < len(lines) and cont.match(lines[i]):
                buf.append(cont.match(lines[i]).group(1))
                i += 1
            out.append('<div class="callout %s">' % ctype)
            if ctitle:
                out.append('<div class="callout-title">%s</div>' % ctitle)
            out.append(" ".join(buf))
            out.append("</div>")
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def find_published():
    notes = []
    for root, _, files in os.walk(VAULT):
        for f in files:
            if not f.lower().endswith(".md"):
                continue
            p = os.path.join(root, f)
            try:
                text = open(p, encoding="utf-8").read()
            except Exception:
                continue
            fm, _ = split_frontmatter(text)
            if fm.get("publish", "").lower() not in ("true", "1", "yes"):
                continue
            src_rel = os.path.relpath(p, VAULT)
            raw = fm.get("section") or section_for(src_rel)
            section = CAMEL_TO_LOWER.get(raw, raw)
            if section not in KNOWN_SECTIONS:
                print("  [跳过] 未知 section: %s (%s)" % (section, src_rel))
                continue
            slug = fm.get("slug") or sanitize_slug(f)
            notes.append({"path": p, "src_rel": src_rel, "section": section,
                          "slug": slug, "fm": fm})
    return notes


def copy_images(src_dir, section, needed):
    dst_img = os.path.join(CONTENT, section, "images")
    candidates = [src_dir, os.path.join(src_dir, "images"),
                  os.path.join(VAULT, "90_Attachments", "Images"),
                  os.path.join(VAULT, "90_Attachments")]
    copied = 0
    for base in needed:
        for cd in candidates:
            sp = os.path.join(cd, base)
            if os.path.exists(sp):
                os.makedirs(dst_img, exist_ok=True)
                shutil.copy2(sp, os.path.join(dst_img, base))
                copied += 1
                break
    return copied


def main():
    dry = "--dry" in sys.argv
    tpl = open(TEMPLATE, encoding="utf-8").read()
    notes = find_published()
    print("找到 %d 篇待发布笔记" % len(notes))
    published_map = {}
    for n in notes:
        published_map[n["slug"].lower()] = n["slug"]
        title_key = (n["fm"].get("title") or "").strip().lower()
        if title_key:
            published_map[title_key] = n["slug"]

    for n in notes:
        p, src_dir = n["path"], os.path.dirname(n["path"])
        text = open(p, encoding="utf-8").read()
        fm, body = split_frontmatter(text)
        # 标题
        title = fm.get("title")
        if not title:
            mm = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            if mm:
                title = mm.group(1)
                body = body.replace(mm.group(0), "", 1).lstrip("\n")
        title = title or os.path.splitext(os.path.basename(p))[0]
        # 日期
        date = fm.get("date") or fm.get("created") or fm.get("published") or datetime.date.today().isoformat()
        section = n["section"]
        label = SECTION_LABEL.get(section, section)
        slug = n["slug"]

        md_body, needed = preprocess(body, src_dir, published_map)
        html_body = MD.convert(md_body)
        MD.reset()
        out = (tpl.replace("{{TITLE}}", title)
                  .replace("{{CONTENT}}", html_body)
                  .replace("{{DATE}}", date)
                  .replace("{{SECTION}}", label))
        dst = os.path.join(CONTENT, section, slug + ".html")
        if dry:
            print("  [dry] -> %s" % os.path.relpath(dst, CONTENT))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "w", encoding="utf-8").write(out)
        copied = copy_images(src_dir, section, needed)
        # 删除同名旧 .md，避免 Quartz 双重渲染（不删 index.md）
        twin = os.path.join(CONTENT, section, slug + ".md")
        if os.path.exists(twin) and os.path.basename(twin) != "index.md":
            os.remove(twin)
            print("  已生成 %s (图片%d, 删旧md)" % (os.path.relpath(dst, CONTENT), copied))
        else:
            print("  已生成 %s (图片%d)" % (os.path.relpath(dst, CONTENT), copied))


if __name__ == "__main__":
    main()
