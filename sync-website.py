# -*- coding: utf-8 -*-
"""
sync-website.py — 网站同步引擎（08_Website 为唯一源头）

工作流（2026-09-06 定稿）:
  1. 手动从 05_Research 复制需要发布的内容到 08_Website（图片引用路径不规范没关系）
  2. 双击 sync-content.ps1（本引擎）：规范化 08_Website -> robocopy 镜像到 quartz/content
  3. 双击 preview.bat：同步 + 本地预览
  4. 双击 publish.bat：同步 + git 推送 Cloudflare 上线

本引擎做三件事:
  A. 规范化 08_Website（原地，幂等，可反复跑）:
     - images/ 下图片文件名统一 slug 化小写（与 Quartz 构建产物一致）
     - md 里 wikilink/库内全路径/URL编码 的图片引用 -> 相对路径 images/xxx.jpg
     - 跨文件夹引用的图片自动复制进本文件夹 images/（每篇文章自包含）
     - md 里相对 .htm 链接 -> 按 slugify 规则的绝对最终 URL
     - htm 里资源引用与 images/ 实际文件名对齐（小写）
     - 清理误粘贴的 PowerShell 脚本残留
  B. robocopy /MIR 镜像 08_Website -> quartz/content
  C. (--build) 本地构建验证

用法:
  python sync-website.py            # 规范化 + 镜像
  python sync-website.py --dry      # 演练：只打印将做什么，不写任何文件
  python sync-website.py --build    # 同步后 npx quartz build
"""
import os
import re
import sys
import shutil
import subprocess
import urllib.parse

VAULT = r"E:\ObsidianVault"
WEB08 = os.path.join(VAULT, "08_Website")
VAULT_DIRS = ["05_Research", "08_Website"]  # 库内全路径引用可能的开头
QUARTZ = r"E:\Website\quartz"
CONTENT = os.path.join(QUARTZ, "content")

dry = "--dry" in sys.argv
warnings = []
actions = []


def log(m):
    print(m, flush=True)


def act(m):
    actions.append(m)
    log(("  [dry] " if dry else "  ") + m)


# ---------- slug 规则（与 Quartz slugifyFilePath 对齐的固定点） ----------

def web_slug(name):
    """文件/文件夹名 -> Quartz slugify 后的确定形态（小写，保留下划线，空格转连字符）。"""
    stem, ext = os.path.splitext(name)
    s = stem.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s]+", "-", s)           # 只转空格；下划线 Quartz 会保留
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s + ext.lower()


def final_htm_url(target_folder, htm_filename):
    """htm 在构建后的最终绝对 URL（含 folder==stem -> index 规则）。"""
    d = os.path.splitext(web_slug(target_folder))[0] or "folder"
    n = os.path.splitext(web_slug(htm_filename))[0]
    if n == d:
        n = "index"
    return "/%s/%s/%s.htm" % (target_folder, d, n)


# ---------- PowerShell 脚本残留清理 ----------

DEBRIS_PATTERNS = [
    "param($", "$oldPath", "$oldName", "$renameMap", "$match.Value",
]


def strip_debris(text):
    lines = text.split("\n")
    out = [l for l in lines if not any(p in l for p in DEBRIS_PATTERNS)]
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# ---------- 图片文件定位工具 ----------

def slugify_file(name):
    """图片文件名 slug 化（图片扩展名小写，stem 小写连字符）。"""
    return web_slug(name)


def case_insensitive_find(directory, basename):
    """在 directory 的 images/ 里按大小写不敏感找文件，返回实际文件名。"""
    img_dir = os.path.join(directory, "images")
    if not os.path.isdir(img_dir):
        return None
    target = os.path.basename(basename).lower()
    for fn in os.listdir(img_dir):
        if fn.lower() == target:
            return fn
    return None


def rename_images_to_slug(folder):
    """images/ 下文件重命名为 slug 化名字（幂等）。返回 {lower_old: new}。"""
    img_dir = os.path.join(folder, "images")
    if not os.path.isdir(img_dir):
        return {}
    mapping = {}
    for fn in sorted(os.listdir(img_dir)):
        new = slugify_file(fn)
        if fn == new:
            mapping[fn.lower()] = fn
            continue
        src = os.path.join(img_dir, fn)
        dst = os.path.join(img_dir, new)
        if os.path.exists(dst) and os.path.abspath(src) != os.path.abspath(dst):
            # 目标已存在（大小写变换或重名）：NTFS 上同名不同大小写需两步
            tmp = os.path.join(img_dir, "__tmp__" + new)
            if not dry:
                os.rename(src, tmp)
                os.rename(tmp, dst)
        else:
            if not dry:
                os.rename(src, dst)
        mapping[fn.lower()] = new
        act("重命名图片: %s/images/%s -> %s" % (os.path.basename(folder), fn, new))
    return mapping


def find_vault_file(rel_path):
    """按 vault 全路径定位文件（大小写不敏感逐段匹配）。返回绝对路径或 None。"""
    p = urllib.parse.unquote(rel_path).replace("\\", "/").lstrip("/")
    # 归一化 vault 内路径
    for head in VAULT_DIRS:
        if p.lower().startswith(head.lower() + "/"):
            cur = VAULT
            parts = [x for x in p.split("/") if x]
            ok = True
            for part in parts:
                nxt = None
                try:
                    entries = os.listdir(cur)
                except OSError:
                    ok = False
                    break
                for e in entries:
                    if e.lower() == part.lower():
                        nxt = os.path.join(cur, e)
                        break
                if nxt is None:
                    ok = False
                    break
                cur = nxt
            if ok and os.path.isfile(cur):
                return cur
    return None


_vault_name_index = None


def search_vault_by_name(basename):
    """全 vault 按文件名搜索（大小写不敏感），带缓存。返回绝对路径或 None。"""
    global _vault_name_index
    target = basename.lower()
    if _vault_name_index is None:
        _vault_name_index = {}
        for root, dirs, files in os.walk(VAULT):
            dirs[:] = [d for d in dirs if d not in (".git", ".obsidian", ".workbuddy")]
            for fn in files:
                _vault_name_index.setdefault(fn.lower(), []).append(os.path.join(root, fn))
    hits = _vault_name_index.get(target, [])
    return hits[0] if hits else None


def import_image_to_folder(folder, abs_src):
    """把外部图片复制进 folder/images/（slug 名），返回新文件名。"""
    img_dir = os.path.join(folder, "images")
    new_name = slugify_file(os.path.basename(abs_src))
    dst = os.path.join(img_dir, new_name)
    if not os.path.isdir(img_dir):
        if not dry:
            os.makedirs(img_dir, exist_ok=True)
    if not os.path.exists(dst):
        if not dry:
            shutil.copy2(abs_src, dst)
        act("导入跨文件夹图片: %s -> %s/images/%s" % (
            os.path.basename(os.path.dirname(abs_src)), os.path.basename(folder), new_name))
    return new_name


# ---------- md / htm 引用改写 ----------

IMG_REF_MD = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")
WIKILINK_EMBED = re.compile(r"(!\[\[)([^\]|]+)(?:\|([^\]]*))?(\]\])")
MD_HTM_LINK = re.compile(r"\]\(([^):]+\.html?)\)", re.IGNORECASE)
HTM_REF = re.compile(
    r"""(\b(?:src|srcset|data-src|href)\s*=\s*)(["'])([^"']+)(\2)""", re.IGNORECASE)


def resolve_image_ref(folder, raw):
    """解析一条图片引用。返回 images/ 文件名、"KEEP"（健康路径保留原样）或 None。"""
    raw_dec = urllib.parse.unquote(raw.strip()).replace("\\", "/")
    # 0) 健康的相对路径（../ 或 ./）且文件确实存在 -> Quartz 会自动改写，保留原样
    if raw_dec.startswith(("../", "./")):
        if os.path.exists(os.path.join(folder, raw_dec)):
            return "KEEP"
    # 1) 已是本文件夹相对引用
    if not raw_dec.startswith("/") and "/" not in raw_dec:
        hit = case_insensitive_find(folder, raw_dec)
        if hit:
            return hit
    # 2) 引用里含 images/ 取 basename
    base = os.path.basename(raw_dec)
    hit = case_insensitive_find(folder, base)
    if hit:
        return hit
    # 3) vault 全路径 -> 定位实际文件 -> 复制进来
    abs_f = find_vault_file(raw_dec)
    if abs_f:
        return import_image_to_folder(folder, abs_f)
    # 4) 引用其他文章文件夹（如 research/xxx/images/yyy.jpg 或 nail-disease/xxx/images/yyy.jpg）
    m = re.search(r"(?:research|nail-disease|education|clinical)/[^/]+/images/([^/]+)$", raw_dec, re.IGNORECASE)
    if m:
        hit = case_insensitive_find(folder, m.group(1))
        if hit:
            return hit
    # 5) 全 vault 按文件名搜（Obsidian 纯文件名 wikilink）
    abs_f = search_vault_by_name(base)
    if abs_f:
        return import_image_to_folder(folder, abs_f)
    return None


def normalize_md(folder, rel_folder, fn):
    path = os.path.join(folder, fn)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    orig = text

    def sub_wikilink(m):
        target = m.group(2).strip()
        alias = m.group(3)
        hit = resolve_image_ref(folder, target)
        if hit == "KEEP":
            return m.group(0)
        if hit:
            alt = alias or os.path.splitext(hit)[0]
            return "![%s](images/%s)" % (alt, hit)
        warnings.append("未解析 wikilink 引用: %s/%s -> ![[%s]]" % (rel_folder, fn, target[:80]))
        return m.group(0)

    def sub_img(m):
        raw = m.group(2).strip()
        if raw.startswith(("http://", "https://", "data:")):
            return m.group(0)
        hit = resolve_image_ref(folder, raw)
        if hit == "KEEP":
            return m.group(0)
        if hit:
            return "%simages/%s%s" % (m.group(1), hit, m.group(3))
        warnings.append("未解析图片引用: %s/%s -> %s" % (rel_folder, fn, raw[:80]))
        return m.group(0)

    def sub_htm_link(m):
        url = m.group(1).strip()
        if url.startswith(("/", "http://", "https://", "#")):
            return m.group(0)
        htm_name = os.path.basename(urllib.parse.unquote(url))
        final = final_htm_url(rel_folder, htm_name)
        if not url.endswith(final):
            act("改写 htm 链接: %s/%s ](%s) -> ](%s)" % (rel_folder, fn, url, final))
        return "](%s)" % final

    text = WIKILINK_EMBED.sub(sub_wikilink, text)
    text = IMG_REF_MD.sub(sub_img, text)
    text = MD_HTM_LINK.sub(sub_htm_link, text)

    cleaned = strip_debris(text)
    if cleaned != orig:
        if not dry:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(cleaned)
        act("规范化 md: %s/%s" % (rel_folder, fn))


def normalize_htm(folder, rel_folder, fn):
    path = os.path.join(folder, fn)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    orig = text
    img_dir = os.path.join(folder, "images")
    actual = {fn2.lower(): fn2 for fn2 in (os.listdir(img_dir) if os.path.isdir(img_dir) else [])}

    def sub_ref(m):
        attr, quote, url, quote2 = m.groups()
        if url.startswith(("http://", "https://", "data:", "//", "#", "mailto:")):
            return m.group(0)
        dec = urllib.parse.unquote(url)
        base = os.path.basename(dec.split("?")[0].split("#")[0])
        stem, ext = os.path.splitext(base)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js"):
            return m.group(0)
        hit = actual.get(base.lower())
        if hit is None:
            warnings.append("htm 引用找不到文件: %s/%s -> %s" % (rel_folder, fn, base))
            return m.group(0)
        new_base = hit
        if dec == base or "/" not in dec:
            new_url = new_base
        else:
            new_url = url[: url.rfind("/") + 1] + new_base
        if new_url != url:
            act("对齐 htm 资源引用: %s/%s %s -> %s" % (rel_folder, fn, base, new_base))
            return "%s%s%s%s" % (attr, quote, new_url, quote2)
        return m.group(0)

    text = HTM_REF.sub(sub_ref, text)
    if text != orig:
        if not dry:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        act("规范化 htm: %s/%s" % (rel_folder, fn))


# ---------- 主流程 ----------

def normalize_tree():
    log("== 步骤 1: 规范化 08_Website ==")
    seen_folders = set()
    for root, dirs, files in os.walk(WEB08):
        dirs[:] = [d for d in dirs if d not in (".obsidian", ".git")]
        rel = os.path.relpath(root, WEB08)
        rel_folder = "" if rel == "." else rel.replace("\\", "/")
        # 每个文件夹只做一次图片 slug 化重命名（在改写引用之前）
        if root not in seen_folders:
            seen_folders.add(root)
            rename_images_to_slug(root)
        for fn in sorted(files):
            low = fn.lower()
            if low.endswith(".md"):
                normalize_md(root, rel_folder, fn)
            elif low.endswith(".htm") or low.endswith(".html"):
                normalize_htm(root, rel_folder, fn)
    # 遗留 manifest 清理
    manifest = os.path.join(WEB08, ".research-sync.json")
    if os.path.exists(manifest):
        if not dry:
            os.remove(manifest)
        act("删除遗留 manifest: .research-sync.json")


def align_case():
    """NTFS 大小写不敏感导致 robocopy 保留 content 旧名；对齐 content 与 08 的文件名大小写。"""
    log("== 步骤 2.5: 对齐 content 文件名大小写 ==")
    if dry:
        log("  [dry] 对齐大小写")
        return
    fixed = 0
    for root, dirs, files in os.walk(WEB08):
        dirs[:] = [d for d in dirs if d not in (".obsidian", ".git")]
        rel = os.path.relpath(root, WEB08)
        croot = os.path.join(CONTENT, rel)
        if not os.path.isdir(croot):
            continue
        for name in files + dirs:
            actual_in_content = None
            try:
                entries = os.listdir(croot)
            except OSError:
                continue
            for e in entries:
                if e.lower() == name.lower():
                    actual_in_content = e
                    break
            if actual_in_content is not None and actual_in_content != name:
                src = os.path.join(croot, actual_in_content)
                dst = os.path.join(croot, name)
                tmp = dst + "__case__"
                try:
                    if os.path.isfile(src):
                        os.rename(src, tmp)
                        os.rename(tmp, dst)
                        fixed += 1
                    elif os.path.isdir(src) and not os.listdir(src):
                        os.rename(src, tmp)
                        os.rename(tmp, dst)
                        fixed += 1
                except OSError:
                    pass
    log("  对齐 %d 个文件/文件夹名" % fixed)


def mirror():
    log("== 步骤 2: robocopy /MIR 08_Website -> content ==")
    cmd = ["robocopy", WEB08, CONTENT, "/MIR", "/XD", ".obsidian", ".git",
           "/XF", "*.canvas", "workspace.json", ".research-sync.json", "/NFL", "/NDL", "/NJH", "/NJS"]
    if dry:
        log("  [dry] " + " ".join(cmd))
        return
    r = subprocess.run(cmd, capture_output=True)
    rc = r.returncode
    if rc < 8:
        log("  镜像完成 (robocopy rc=%d)" % rc)
    else:
        log("  镜像失败 rc=%d" % rc)
        sys.exit(rc)


def build():
    log("== 步骤 3: npx quartz build ==")
    if dry:
        log("  [dry] npx quartz build")
        return
    r = subprocess.run(["cmd", "/c", "npx quartz build"], cwd=QUARTZ, capture_output=True)
    out = r.stdout.decode(errors="replace")
    tail = "\n".join(out.strip().split("\n")[-6:])
    log(tail)


def main():
    log("sync-website: 08_Website 规范化 + 镜像%s" % ("（演练模式）" if dry else ""))
    normalize_tree()
    mirror()
    align_case()
    if "--build" in sys.argv:
        build()
    log("")
    if warnings:
        log("⚠ 未解析引用 %d 条（需手动处理）:" % len(warnings))
        for w in warnings:
            log("  - " + w)
    else:
        log("✓ 所有引用可解析")
    log("完成。下一步: 预览双击 preview.bat / 发布双击 publish.bat")


if __name__ == "__main__":
    main()
