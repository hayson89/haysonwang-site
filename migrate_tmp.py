# -*- coding: utf-8 -*-
import os, shutil

SRC = "E:/ObsidianVault"
DST = "E:/Website/quartz/content"
AK = "03_Disease_based_learning/02_Foot_Ankle/02_甲沟炎"

# (src_rel, dst_folder, dst_name, title_or_None)
migrations = [
    ("Clippings/【安理大一附院】不开刀，不拔甲，钢丝矫正器也能治疗甲沟炎！.md",
     "Medical_Education", "anli-yiyuan-gangjia.md", None),
    ("Clippings/【甲病专科门诊】告别“嵌甲”之痛——甲沟炎防治早知道.md",
     "Medical_Education", "jiabing-zhuanke-menzen.md", None),
    ("Clippings/【科普小知识】那些“触目惊心”的趾甲——甲沟炎的门诊治疗.md",
     "Medical_Education", "kepu-xiaozhishi.md", None),
    (AK + "/不拔甲的理由.md", "Nail_Disorders", "baba-jia-deliyou.md", "不拔甲的理由"),
    (AK + "/won2019牙科用胶水镍钛钢丝.md", "Nail_Disorders", "won2019-nieti-gangsi.md",
     "镍钛钢丝矫正甲板畸形的疗效影响因素（Won 2019）"),
    ("06_Teaching/单日甲沟炎手术记录.md", "Clinical_Practice", "danzi-jiagouyan-shoushu.md",
     "单日甲沟炎手术记录"),
    (AK + "/Controversies in the Treatment of Ingrown Nails (2012).md", "Medical_Research",
     "controversies-ingrown-nails-2012.md", "Controversies in the Treatment of Ingrown Nails (2012)"),
    (AK + "/Chapeskie vandenbos.md", "Medical_Research", "chapeskie-vandenbos.md",
     "Chapeskie-Vandenbos 术式：Overgrown Toeskin 理论与软组织治疗体系"),
]

WIKILINK_FIX = "[[市一院小儿外科]]", "市一院小儿外科"

for src_rel, folder, name, title in migrations:
    sp = os.path.join(SRC, src_rel)
    dp = os.path.join(DST, folder, name)
    os.makedirs(os.path.dirname(dp), exist_ok=True)
    with open(sp, encoding="utf-8") as f:
        text = f.read()
    # fix wikilink (harmless if absent)
    text = text.replace(*WIKILINK_FIX)
    # ensure frontmatter title
    if not text.lstrip().startswith("---"):
        text = '---\ntitle: "%s"\n---\n\n' % title + text
    with open(dp, "w", encoding="utf-8") as f:
        f.write(text)
    print("MIGRATED:", src_rel, "->", os.path.join(folder, name))

# copy won2019 local images
img_src = os.path.join(SRC, AK, "images")
img_dst = os.path.join(DST, "Nail_Disorders", "images")
os.makedirs(img_dst, exist_ok=True)
copied = 0
for fn in os.listdir(img_src):
    if fn.lower().endswith(".jpg"):
        shutil.copy2(os.path.join(img_src, fn), os.path.join(img_dst, fn))
        copied += 1
print("COPIED images:", copied)

# hub index.md for 3 sections (Medical_Education index = renamed existing article)
hubs = {
    "Nail_Disorders": "# 甲病专科 · Nail Disorders\n\n围绕甲沟炎、嵌甲及相关甲病的疾病认识、保守治疗与手术方式，整理诊疗思路与文献要点。\n",
    "Clinical_Practice": "# 临床实践 · Clinical Practice\n\n记录典型病例、治疗过程与随访变化，持续总结临床实践中的问题与经验。\n",
    "Medical_Research": "# 从基础到临床 · Medical Research\n\n学习经典著作、最新文献解读以及研究进展。\n",
}
for folder, body in hubs.items():
    p = os.path.join(DST, folder, "index.md")
    if os.path.exists(p):
        print("SKIP hub (exists):", folder)
        continue
    with open(p, "w", encoding="utf-8") as f:
        f.write(body)
    print("HUB created:", folder)

# rename existing 甲沟炎 article -> Medical_Education/index.md (landing page)
old = os.path.join(DST, "Medical_Education", "甲沟炎去医院：看哪个科室？.md")
new = os.path.join(DST, "Medical_Education", "index.md")
if os.path.exists(old) and not os.path.exists(new):
    os.rename(old, new)
    print("RENAMED landing:", old, "->", new)
else:
    print("LANDING rename skipped (old exists?%s new exists?%s)" % (os.path.exists(old), os.path.exists(new)))

# remove Docsify leftovers
for fn in ["index.html", "_sidebar.md"]:
    p = os.path.join(DST, fn)
    if os.path.exists(p):
        os.remove(p)
        print("REMOVED leftover:", fn)
    else:
        print("leftover not found:", fn)

print("DONE")
