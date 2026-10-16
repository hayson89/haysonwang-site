---
title: 随访系统 FollowUp
---

<style>
.followup-entry {
  max-width: 640px;
  margin: 1.5rem auto;
  text-align: center;
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.followup-entry h2 {
  color: #284b63;
  font-weight: 700;
}
.followup-btn {
  display: inline-block;
  margin-top: 1.2rem;
  padding: 0.75rem 1.6rem;
  background: #284b63;
  color: #fff;
  border-radius: 0.5rem;
  text-decoration: none;
  font-weight: 600;
  transition: background 0.2s;
}
.followup-btn:hover { background: #1d3647; }
.followup-hint { color: #888; font-size: 0.9rem; margin-top: 1rem; }
</style>

<div class="followup-entry">
  <h2>🩺 随访管理系统</h2>
  <p>患者随访与术后管理平台（FollowUp System）。点击下方按钮，或直接在左侧目录点击「随访系统」即可进入。</p>
  <a class="followup-btn" href="https://followup.haysonwang.com" target="_blank" rel="noopener">进入随访系统 →</a>
  <p class="followup-hint">提示：系统部署在独立服务器，将以新标签页打开。</p>
</div>

<script>
  // https -> https 同源跳转，浏览器允许；若被拦截，上方按钮仍可手动进入
  window.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
      window.location.href = 'https://followup.haysonwang.com';
    }, 600);
  });
</script>
