# -*- coding: utf-8 -*-
"""
sync-research.py — 一条命令完成整条发布链路

  05_Research(文献库) --> 08_Website/research(中转) --> quartz/content(镜像) --> [build] --> [push]

自动完成 4 项改写(不再需要手动改):
  1. 图片文件名 slug 化(小写、空格->连字符), 与 Quartz 构建后的实际文件名一致
  2. md 里的库内全路径引用(05_Research/.../IMG_1.jpg、08_Website/...) 改写为相对路径 images/xxx.jpg
  3. md 里指向本地 .htm 幻灯片的链接, 自动改写为 slugify 后的线上绝对路径(/research/xxx/index.htm)
  4. 清理 md 里残留的 PowerShell 脚本碎片(param($match)/renameMap 等)

用法:
  python sync-research.py            # 同步到 08_Website + 镜像到 content + 运行 publish.py
  python sync-research.py --dry      # 只打印将要做什么, 不写任何文件
  python sync-research.py --build    # 同上 + npx quartz build
  python sync-research.py --push     # 同上 + git 提交推送(08_Website 本地仓库 + quartz 远程)

注意:
  - 08_Website/research 里已有的手工文件(中文导读 md、手工命名的 htm)不会被覆盖;
    脚本只改写它们内部的图片引用, 使之与实际图片文件名匹配。
  - 想排除某篇文献: 把文件夹名(或散置 md 文件名)加入下面 SKIP 集合, 或在源 md frontmatter 写 publish: false
  - 已上线文章的文件夹名固定在 ARTICLE_MAP 里, 不要改(改了线上 URL 会变)。
"""

import os
import re
import sys
import json
import shutil
import hashlib
import subprocess
import urllib.parse

# ============ 配置区(按需修改) ============

VAULT = "E:/ObsidianVault"
SRC = os.path.join(VAULT, "05_Research")
WEB08 = os.path.join(VAULT, "08_Website")
QUARTZ = "E:/Website/quartz"
CONTENT = os.path.join(QUARTZ, "content")
PUBLISH_PY = os.path.join(QUARTZ, "publish.py")
MANIFEST = os.path.join(WEB08, ".research-sync.json")

# 源文件夹名 -> 08_Website/research 下的目标文件夹名(已上线, 固定不动; 改动会导致线上 URL 变化)
# 新文献不需要加: 默认按文件夹名自动 slug 化
ARTICLE_MAP = {
    "Tardy PIN Palsy Monteggia Fracture": "tardy_PIN",
    "2020_Use of bone wax as a nail bed dressing after excision of subungual tumors": "2020_Use of bone wax",
    "Uygur 2014 改良缝合法 a new and simple suturing technique 2014": "newsuturing2014",
}

# 不想发布到网站的条目(源文件夹名, 或 05_Research 根目录的散置 md 文件名)
SKIP = {
    "EMLA趾根阻滞 发表策略与RCT方案构思.md",  # 内部发表策略笔记, 不公开
    "99_内部资料",  # 课题构思/待转换PDF等内部资料, 不公开 (2026-09-06 归档时新增)
}

# ========================================

IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp")
PS_DEBRIS = ("param($", "$oldPath", "$oldName", "$renameMap", "$match.Value")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg):
    print(msg, flush=True)


# ---------- slug: 让 Quartz 的 slugify 成为空操作 ----------

def web_slug(name):
    """文件/文件夹名 -> web 安全名(小写、空格转-、去不安全字符、保留中文和下划线)。
    保证 Quartz slugify(结果) == 结果, 从而本地文件名 = 线上文件名。"""
    stem, ext = os.path.splitext(name)
    s = stem.replace("&", " and ").lower()
    s = re.sub(r"[^\w\s-]", "", s)          # \w 含中文; 去掉括号引号冒号等
    s = re.sub(r"[\s]+", "-", s)            # 空格 -> -
    s = re.sub(r"-{2,}", "-", s).strip("-_")
    ext = ext.lower()
    return (s or "file") + ext


def final_htm_url(target_folder, htm_filename):
    """md 里指向 htm 的链接最终应写的线上绝对路径(含 index 规则: 文件名与文件夹同名 -> index.htm)。"""
    d = os.path.splitext(web_slug(target_folder))[0] or "folder"
    f = web_slug(htm_filename)
    stem = os.path.splitext(f)[0]
    name = "index.htm" if stem == d else f
    return "/research/%s/%s" % (d, name)


# ---------- md 改写 ----------

def strip_debris(text):
    lines = [ln for ln in text.split("\n") if not any(p in ln for p in PS_DEBRIS)]
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return out


def read_file(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_file(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def rewrite_md_images(text, img_map, src_path_map, warns, where):
    """img_map: {小写文件名: 相对md的路径}; src_path_map: {源全路径(小写): 相对md的路径}"""
    def emb(m):
        inner = m.group(1)
        parts = inner.split("|")
        raw = parts[0].strip()
        alias = parts[1].strip() if len(parts) > 1 else ""
        dec = urllib.parse.unquote(raw).replace("\\", "/").lower()
        base = os.path.basename(dec)
        if dec in src_path_map:
            rel = src_path_map[dec]
        elif base in img_map:
            rel = img_map[base]
        elif base.endswith(IMG_EXT):
            warns.append("[图片未找到] %s <- %s" % (raw, where))
            return m.group(0)
        else:
            return m.group(0)  # 非图片的 wikilink, 交给 Quartz 处理
        alt = alias or os.path.splitext(os.path.basename(rel))[0]
        return "![%s](%s)" % (alt, rel)

    text = re.sub(r"!\[\[([^\]]+)\]\]", emb, text)

    def img(m):
        alt, raw = m.group(1), m.group(2)
        if raw.startswith(("http://", "https://", "data:", "#", "/")):
            return m.group(0)
        dec = urllib.parse.unquote(raw).replace("\\", "/").lower()
        base = os.path.basename(dec)
        if dec in src_path_map:
            return "![%s](%s)" % (alt, src_path_map[dec])
        if base in img_map:
            return "![%s](%s)" % (alt, img_map[base])
        if base.endswith(IMG_EXT):
            warns.append("[图片未找到] %s <- %s" % (raw, where))
        return m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img, text)


def rewrite_md_htm_links(text, htm_url_map, warns, where):
    """把 ](xxx.htm) 相对链接改成线上绝对路径。htm_url_map: {小写文件名: 绝对URL}"""
    def repl(m):
        raw = m.group(1)
        if raw.startswith(("http", "/", "#", "data:", "mailto:")):
            return m.group(0)
        base = os.path.basename(urllib.parse.unquote(raw).replace("\\", "/")).lower()
        if base in htm_url_map:
            return "(%s)" % htm_url_map[base]
        warns.append("[htm未找到] %s <- %s" % (raw, where))
        return m.group(0)

    return re.sub(r"\]\(([^)]+\.html?)\)", repl, text)


def rewrite_htm_refs(text, img_map, warns, where):
    """htm 是原样复制的, 内部引用必须与实际文件名完全一致。"""
    def fix_val(val):
        if val.startswith(("http://", "https://", "data:", "#", "/", "//")):
            return None
        dec = urllib.parse.unquote(val).replace("\\", "/")
        base = os.path.basename(dec)
        hit = img_map.get(base.lower())
        if hit:
            new = os.path.join(os.path.dirname(dec), os.path.basename(hit)).replace("\\", "/")
            return new if new != dec else None
        if base.lower().endswith(IMG_EXT):
            warns.append("[htm图片未找到] %s <- %s" % (val, where))
        return None

    def attr(m):
        val = m.group(2)
        nv = fix_val(val)
        return m.group(0) if nv is None else '%s="%s"' % (m.group(1), nv)

    text = re.sub(r'\b(src|srcset|data-src|href)\s*=\s*"([^"]+)"', attr, text)

    def css(m):
        val = m.group(1).strip("'\"")
        nv = fix_val(val)
        return m.group(0) if nv is None or nv == val else "url(%s)" % nv

    return re.sub(r"url\(([^)]+)\)", css, text)


# ---------- 工具 ----------

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def frontmatter_publish_false(p):
    try:
        text = read_file(p)
    except Exception:
        return False
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return False
    return re.search(r"^\s*publish\s*:\s*false", m.group(1), re.MULTILINE) is not None


# ---------- 主流程 ----------

def transform(dry, warns):
    """05_Research -> 08_Website/research, 返回新建/更新的目标文件清单(manifest)"""
    if not os.path.isdir(SRC):
        log("[错误] 源目录不存在: " + SRC)
        sys.exit(1)
    tgt_root = os.path.join(WEB08, "research")
    os.makedirs(tgt_root, exist_ok=True)

    old_manifest = {}
    if os.path.exists(MANIFEST):
        try:
            old_manifest = json.load(open(MANIFEST, encoding="utf-8")).get("files", {})
        except Exception:
            old_manifest = {}

    new_manifest = {}
    articles = []       # (源文件夹, 目标文件夹绝对路径, 目标文件夹名)
    loose_mds = []

    for name in sorted(os.listdir(SRC)):
        p = os.path.join(SRC, name)
        if name in SKIP or name.startswith("."):
            continue
        if os.path.isdir(p):
            mds = [f for f in os.listdir(p) if f.lower().endswith(".md")]
            if any(frontmatter_publish_false(os.path.join(p, f)) for f in mds):
                log("[跳过] publish:false  " + name)
                continue
            articles.append((p, name))
        elif name.lower().endswith(".md"):
            if frontmatter_publish_false(p):
                log("[跳过] publish:false  " + name)
                continue
            loose_mds.append((p, name))

    # ---- 逐文章处理 ----
    for src_dir, src_name in articles:
        tgt_name = ARTICLE_MAP.get(src_name, web_slug(src_name))
        tgt_dir = os.path.join(tgt_root, tgt_name)
        log("== %s  ->  research/%s" % (src_name, tgt_name))

        img_map = {}        # 小写名 -> 相对md路径 (本文件夹内)
        src_path_map = {}   # 源全路径(小写) -> 相对md路径

        # 1) 目标文件夹里已有的手工图片 -> 先 slug 改名(避免与源复制产生大小写重复)
        if os.path.isdir(os.path.join(tgt_dir, "images")):
            for f in sorted(os.listdir(os.path.join(tgt_dir, "images"))):
                if not f.lower().endswith(IMG_EXT):
                    continue
                fp = os.path.join(tgt_dir, "images", f)
                slug = web_slug(f)
                img_map.setdefault(f.lower(), "images/" + slug)
                if slug == f:
                    continue
                np_ = os.path.join(tgt_dir, "images", slug)
                if not os.path.exists(np_):
                    if not dry:
                        os.rename(fp, np_)
                    log("   [改名] images/%s -> images/%s" % (f, slug))
                elif md5(fp) == md5(np_):
                    # 内容相同的重复文件(如手工复制的大写版): 删掉; 删不掉也不影响构建输出
                    if not dry:
                        try:
                            os.remove(fp)
                            log("   [去重删除] images/%s (与 %s 相同)" % (f, slug))
                        except OSError:
                            log("   [保留重复] images/%s (与 %s 相同, 不影响构建)" % (f, slug))
                else:
                    warns.append("[图片同名不同内容, 两者都保留] research/%s/images/%s" % (tgt_name, f))

        # 2) 图片: 从源复制(全量覆盖, slug 命名)
        for root, _, files in os.walk(src_dir):
            for f in files:
                if f.lower().endswith(IMG_EXT):
                    slug = web_slug(f)
                    rel = "images/" + slug
                    dst = os.path.join(tgt_dir, "images", slug)
                    if not dry:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(os.path.join(root, f), dst)
                    img_map[f.lower()] = rel
                    src_path_map[("05_Research/" + src_name + "/" +
                                  os.path.relpath(os.path.join(root, f), src_dir)).replace("\\", "/").lower()] = rel
                    new_manifest[os.path.relpath(dst, WEB08).replace("\\", "/")] = \
                        os.path.relpath(os.path.join(root, f), VAULT).replace("\\", "/")

        # 3) .htm/.html 幻灯片: 复制为 .htm(Quartz 原样保留 .htm; .html 会被当内容处理)
        htm_url_map = {}   # 小写文件名 -> 线上绝对URL
        tgt_htms = []
        if os.path.isdir(tgt_dir):
            tgt_htms = [f for f in os.listdir(tgt_dir) if f.lower().endswith((".htm", ".html"))]
        for root, _, files in os.walk(src_dir):
            for f in files:
                if f.lower().endswith((".htm", ".html")):
                    if tgt_htms:
                        log("   [保留手工htm] 目标已有 %s, 不覆盖源 %s" % (tgt_htms[0], f))
                        continue
                    slug = web_slug(f)
                    if slug.lower().endswith(".html"):
                        slug = slug[:-5] + ".htm"
                    dst = os.path.join(tgt_dir, slug)
                    if not dry:
                        os.makedirs(tgt_dir, exist_ok=True)
                        shutil.copy2(os.path.join(root, f), dst)
                    new_manifest[os.path.relpath(dst, WEB08).replace("\\", "/")] = \
                        os.path.relpath(os.path.join(root, f), VAULT).replace("\\", "/")
                    tgt_htms.append(slug)
        for f in tgt_htms:
            htm_url_map[f.lower()] = final_htm_url(tgt_name, f)

        # 4) md: 源 md 复制(目标已有 md 则保留手工版)
        src_mds = []
        for root, _, files in os.walk(src_dir):
            for f in files:
                if f.lower().endswith(".md"):
                    src_mds.append(os.path.join(root, f))
        tgt_mds = [f for f in (os.listdir(tgt_dir) if os.path.isdir(tgt_dir) else []) if f.lower().endswith(".md")]
        for sp in src_mds:
            if tgt_mds:
                log("   [保留手工md] 目标已有 %s, 不复制源 %s" % (tgt_mds[0], os.path.basename(sp)))
                break
            slug = web_slug(os.path.basename(sp))
            dst = os.path.join(tgt_dir, slug)
            if not dry:
                write_file(dst, transform_md(read_file(sp), img_map, src_path_map, htm_url_map, warns,
                                             os.path.basename(sp)))
            new_manifest[os.path.relpath(dst, WEB08).replace("\\", "/")] = \
                os.path.relpath(sp, VAULT).replace("\\", "/")
            tgt_mds.append(slug)
            log("   [复制] %s" % slug)

        # 5) 改写目标文件夹里所有 md / htm 的引用
        if not dry and os.path.isdir(tgt_dir):
            for f in os.listdir(tgt_dir):
                fp = os.path.join(tgt_dir, f)
                if f.lower().endswith(".md"):
                    old = read_file(fp)
                    new = transform_md(old, img_map, src_path_map, htm_url_map, warns, f)
                    if new != old:
                        write_file(fp, new)
                elif f.lower().endswith((".htm", ".html")):
                    old = read_file(fp)
                    new = rewrite_htm_refs(old, img_map, warns, f)
                    if new != old:
                        write_file(fp, new)

    # ---- 散置 md(05_Research 根目录) ----
    if loose_mds:
        all_imgs = {}       # 小写名 -> 相对路径(带文件夹前缀)
        all_src_paths = {}  # 源全路径 -> 相对路径
        for d in sorted(os.listdir(tgt_root)):
            sub = os.path.join(tgt_root, d, "images")
            if os.path.isdir(sub):
                for f in os.listdir(sub):
                    if f.lower().endswith(IMG_EXT):
                        all_imgs.setdefault(f.lower(), d + "/images/" + f)
        for src_dir, src_name in articles:
            for root, _, files in os.walk(src_dir):
                for f in files:
                    if f.lower().endswith(IMG_EXT):
                        tgt_name = ARTICLE_MAP.get(src_name, web_slug(src_name))
                        rel = os.path.relpath(os.path.join(root, f), src_dir).replace("\\", "/")
                        all_src_paths[("05_Research/" + src_name + "/" + rel).lower()] = \
                            tgt_name + "/images/" + web_slug(f)
        for sp, name in loose_mds:
            slug = web_slug(name)
            dst = os.path.join(tgt_root, slug)
            if os.path.exists(dst):
                log("[跳过] 已存在 %s" % slug)
                continue
            if not dry:
                write_file(dst, transform_md(read_file(sp), all_imgs, all_src_paths, {}, warns, name))
            new_manifest[os.path.relpath(dst, WEB08).replace("\\", "/")] = \
                os.path.relpath(sp, VAULT).replace("\\", "/")
            log("== [散置md] %s -> research/%s" % (name, slug))

    # ---- 清理: 上次同步生成、这次源里已不存在的文件 ----
    for t in sorted(old_manifest):
        if t not in new_manifest:
            p = os.path.join(WEB08, t)
            if os.path.exists(p):
                log("[清理] 源已删除: " + t)
                if not dry:
                    try:
                        os.remove(p)
                    except OSError as e:
                        warns.append("[清理失败] %s: %s" % (t, e))
    if not dry:
        for root, dirs, files in os.walk(tgt_root, topdown=False):
            if not dirs and not files and root != tgt_root:
                try:
                    os.rmdir(root)
                except OSError:
                    pass
        json.dump({"files": new_manifest}, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return new_manifest


def transform_md(text, img_map, src_path_map, htm_url_map, warns, where):
    text = strip_debris(text)
    text = rewrite_md_images(text, img_map, src_path_map, warns, where)
    text = rewrite_md_htm_links(text, htm_url_map, warns, where)
    return text


def mirror(dry):
    log("\n== 镜像 08_Website -> quartz/content (robocopy /MIR)")
    if dry:
        log("[dry] 跳过镜像")
        return
    cmd = ["robocopy", WEB08, CONTENT, "/MIR", "/XD", ".obsidian", ".git",
           "/XF", "*.canvas", "workspace.json", ".research-sync.json", "/NFL", "/NDL", "/NJH", "/NP"]
    r = subprocess.run(cmd)
    if r.returncode >= 8:
        log("[错误] robocopy 失败, 返回码 %d" % r.returncode)
        sys.exit(1)
    log("镜像完成 (robocopy rc=%d, <8 即成功)" % r.returncode)


def run_publish(dry):
    log("\n== 运行 publish.py (publish:true 笔记)")
    if dry or not os.path.exists(PUBLISH_PY):
        if dry:
            log("[dry] 跳过")
        return
    r = subprocess.run([sys.executable, PUBLISH_PY])
    if r.returncode != 0:
        warns.append("[publish.py 返回码 %d]" % r.returncode)


def run_build(dry):
    log("\n== npx quartz build")
    if dry:
        log("[dry] 跳过")
        return
    r = subprocess.run("npx quartz build", shell=True, cwd=QUARTZ)
    if r.returncode != 0:
        log("[错误] 构建失败")
        sys.exit(1)


def run_push(dry):
    log("\n== git 提交推送")
    if dry:
        log("[dry] 跳过")
        return
    msg = "sync: 05_Research -> 网站 " + __import__("datetime").date.today().isoformat()
    for repo, paths, remote in ((WEB08, ["-A"], False), (QUARTZ, ["content", "sync-research.py", "sync-content.ps1", "publish.py"], True)):
        try:
            subprocess.run(["git", "-C", repo, "add"] + paths, check=True)
            r = subprocess.run(["git", "-C", repo, "commit", "-m", msg], capture_output=True, text=True)
            if "nothing to commit" in (r.stdout + r.stderr):
                log("[%s] 无变更" % repo)
                continue
            if remote:
                subprocess.run(["git", "-C", repo, "push", "origin", "main"], check=True)
                log("[%s] 已推送" % repo)
            else:
                log("[%s] 已本地提交" % repo)
        except subprocess.CalledProcessError as e:
            warns.append("[git失败] %s: %s" % (repo, e))


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    warns = []
    if dry:
        log("***** DRY RUN: 不写任何文件 *****\n")
    transform(dry, warns)
    mirror(dry)
    run_publish(dry)
    if "--build" in sys.argv:
        run_build(dry)
    if "--push" in sys.argv:
        run_push(dry)
    log("\n===== 完成 =====")
    if warns:
        log("\n需人工确认的警告 (%d):" % len(warns))
        for w in warns:
            log("  " + w)
    if "--push" not in sys.argv:
        log("\n下一步: 确认无误后执行  python sync-research.py --push  发布上线")
