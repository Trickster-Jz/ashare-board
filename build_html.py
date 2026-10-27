#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股每日复盘看板 - H5 页面生成
读取 data/*.json，生成单文件 index.html（数据内嵌，可离线打开/分享）
"""

import glob
import json
import os
import datetime as dt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUT = os.path.join(BASE_DIR, 'index.html')

MAX_DAYS = 60


def load_days():
    days = {}
    for p in sorted(glob.glob(os.path.join(DATA_DIR, '*.json'))):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            continue
        if d.get('date'):
            days[d['date']] = d
    keys = sorted(days.keys())[-MAX_DAYS:]
    return [days[k] for k in keys]


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,maximum-scale=1">
<meta name="format-detection" content="telephone=no">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>骄子每日复盘看板</title>
<style>
:root{
  --up:#e0393e; --down:#12a862; --flat:#8b8f9a;
  --bg:#f2f3f5; --card:#fff; --line:#eceff3;
  --t1:#1b1d21; --t2:#5b616b; --t3:#9aa0ab;
  --gold:#c9922e; --blue:#3b6fd4;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--t1);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue","Microsoft YaHei",sans-serif;
  font-size:15px;line-height:1.5;padding-bottom:40px}
.wrap{max-width:760px;margin:0 auto;padding:12px}
header{position:sticky;top:0;z-index:20;background:linear-gradient(135deg,#2b3550,#1d2436);
  color:#fff;padding:14px 14px 12px;box-shadow:0 2px 10px rgba(0,0,0,.12)}
.hd-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.hd-title{font-size:17px;font-weight:700;letter-spacing:.5px}
.hd-sub{font-size:11px;opacity:.65;margin-top:2px}
.hd-date{display:flex;align-items:center;gap:6px;margin-top:10px}
select,.btn{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);color:#fff;
  border-radius:8px;padding:6px 10px;font-size:14px;outline:none}
.btn{padding:6px 11px;cursor:pointer}
.hd-status{display:flex;gap:6px;align-items:center;margin-top:9px;flex-wrap:wrap}
.badge{font-size:11px;padding:2px 8px;border-radius:20px;background:rgba(255,255,255,.16)}
.badge.warn{background:rgba(255,193,7,.9);color:#4a3800;font-weight:600}
section{margin-top:12px}
.card{background:var(--card);border-radius:14px;padding:14px;box-shadow:0 1px 3px rgba(20,25,40,.06)}
h2{font-size:15px;margin:0 0 10px;display:flex;align-items:center;gap:6px;font-weight:700}
h2::before{content:"";width:3px;height:14px;background:var(--blue);border-radius:2px}
h2 small{font-weight:400;font-size:11px;color:var(--t3)}

/* 指数 */
.idx-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.idx{border:1px solid var(--line);border-radius:12px;padding:10px 11px;background:#fff}
.idx .n{font-size:13px;color:var(--t2)}
.idx .c{font-size:22px;font-weight:700;margin:3px 0 1px;font-variant-numeric:tabular-nums}
.idx .d{font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
.idx .m{font-size:11px;color:var(--t3);margin-top:6px;font-variant-numeric:tabular-nums}
.idx-split{display:flex;gap:10px;margin-top:8px;border-top:1px dashed var(--line);padding-top:7px}
.idx-split>div{flex:1;min-width:0}
.idx-lab{font-size:11px;color:var(--t3);margin-bottom:2px}
.idx-lab.up{color:var(--up);font-weight:700}
.idx-lab.down{color:var(--down);font-weight:700}
.idx-lab.flat{color:var(--t3)}
.idx-split .m{margin-top:2px}

/* 热点题材表：数值列与表头居中对齐 */
#blocks th.num,#blocks td.num{text-align:center}

/* 排序切换 */
.seg{display:flex;gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;width:max-content;margin-bottom:8px}
.seg button{border:none;background:#f7f8fa;color:var(--t2);font-size:12px;padding:6px 12px;cursor:pointer}
.seg button.on{background:var(--blue);color:#fff;font-weight:600}

/* 龙虎榜折叠 */
.lhb-item{cursor:pointer}
.lhb-h .arr{font-size:15px;color:#fff;background:var(--blue);border-radius:8px;
  padding:3px 10px;margin-left:4px;line-height:1.6;transition:transform .2s,background .2s,color .2s}
.lhb-item.open .arr{transform:rotate(180deg);background:#eef0f4;color:var(--t2)}
.lhb-b{display:none;margin-top:8px}
.lhb-item.open .lhb-b{display:block}

/* 近7日对比 */
.hwrap{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.hwrap::-webkit-scrollbar{display:none}
.htable{min-width:660px;font-size:12px}
.htable th{white-space:nowrap;padding:7px 4px}
.htable th.num{text-align:right}
.htable td{white-space:nowrap;padding:7px 4px}
/* 横向滚动滑块 */
.hbar{position:relative;height:5px;background:#e9ecf1;border-radius:3px;margin-top:9px}
.hbar i{position:absolute;top:0;height:5px;background:var(--blue);border-radius:3px;transition:left .08s linear}
.htable td.date{font-weight:700}
.htable tr.today td{background:#fff8e6}
.frac-up{color:var(--up);font-weight:600}
.frac-down{color:var(--down);font-weight:600}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--flat)}

/* 总览 */
.ov-row{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0;border-bottom:1px dashed var(--line)}
.ov-row:last-child{border-bottom:none}
.ov-lab{font-size:13px;color:var(--t2)}
.ov-val{font-size:17px;font-weight:700;font-variant-numeric:tabular-nums}
.ov-cmp{font-size:11px;color:var(--t3);margin-left:6px;font-weight:400}
.bar{display:flex;height:26px;border-radius:6px;overflow:hidden;margin:8px 0 6px;background:var(--line)}
.bar i{display:block;height:100%}
.b-up{background:var(--up)} .b-flat{background:#c4c8cf} .b-down{background:var(--down)}
.legend{display:flex;justify-content:space-between;font-size:12px;font-variant-numeric:tabular-nums}
.legend b{font-weight:700}
.kv{display:flex;gap:14px;flex-wrap:wrap}
.kv div{font-size:13px;color:var(--t2)}

/* 题材 */
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-weight:600;color:var(--t2);font-size:12px;padding:6px 4px;border-bottom:1px solid var(--line)}
td{padding:8px 4px;border-bottom:1px solid var(--line);vertical-align:middle}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;font-size:11px;background:#f0f2f6;color:var(--t2);border-radius:4px;padding:1px 5px;margin-right:4px}
.stk{font-size:11px;color:var(--t3)}

/* 梯队 */
.lad{margin-bottom:10px}
.lad-h{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.lv{background:var(--up);color:#fff;font-weight:700;font-size:12px;padding:2px 8px;border-radius:5px;border:1px solid var(--up)}
.lv.hot{background:var(--up);color:#fff;border-color:var(--up)}
.lad-c{font-size:12px;color:var(--t3)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{background:#fafbfc;border:1px solid var(--line);border-radius:8px;padding:5px 8px;font-size:12px;line-height:1.35}
.chip b{font-weight:700}
.chip .r{color:var(--t3);font-size:11px;display:block}

/* 龙虎榜 */
.lhb-item{border:1px solid var(--line);border-radius:12px;padding:11px;margin-bottom:10px}
.lhb-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.lhb-n{font-weight:700;font-size:15px}
.lhb-t{font-size:11px;color:var(--t3);margin:3px 0 8px;line-height:1.4}
.seats{display:grid;grid-template-columns:1fr;gap:8px}
.seat-box{background:#fafbfc;border-radius:9px;padding:8px}
.seat-box h4{margin:0 0 5px;font-size:12px;color:var(--t2);font-weight:600}
.srow{display:flex;justify-content:space-between;gap:8px;font-size:12px;padding:3px 0;font-variant-numeric:tabular-nums}
.sname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.inst{color:#3b6fd4;font-size:10px;background:#eaf0fc;border-radius:3px;padding:0 4px;margin-left:3px}
.north{color:#b07d17;font-size:10px;background:#fdf3e0;border-radius:3px;padding:0 4px;margin-left:3px}
.yz{color:#c2410c;font-size:10px;background:#ffeee4;border-radius:3px;padding:0 4px;margin-left:3px}
.money{color:var(--t1);font-weight:600}
.more{display:block;width:100%;background:#f5f6f8;border:none;border-radius:10px;padding:10px;
  font-size:14px;color:var(--blue);cursor:pointer;margin-top:4px}

/* 图表 */
.chart-box{margin-bottom:6px}
.chart-hd{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}
.chart-hd .t{font-size:13px;color:var(--t2);font-weight:600}
.chart-hd .v{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}
.chart-hd .c{font-size:12px;font-variant-numeric:tabular-nums}
svg{display:block;width:100%;height:130px}
footer{text-align:center;font-size:11px;color:var(--t3);margin:18px 12px 0;line-height:1.7}
.empty{color:var(--t3);font-size:13px;padding:14px 0;text-align:center}
.hint{font-size:11px;color:var(--t3);margin-top:6px;line-height:1.6}
</style>
</head>
<body>
<header>
  <div class="hd-top">
    <div>
      <div class="hd-title">骄子每日复盘看板</div>
      <div class="hd-sub">盘中每小时更新数据　21:00 正式存档</div>
    </div>
    <div style="display:flex;gap:6px">
      <button class="btn" id="prev">‹</button>
      <button class="btn" id="next">›</button>
    </div>
  </div>
  <div class="hd-date">
    <select id="dateSel"></select>
  </div>
  <div class="hd-status" id="status"></div>
</header>

<div class="wrap">
  <section><div class="card" id="sec-overview"><h2>市场总览 <small>括号内为上一交易日数据</small></h2>
    <div id="overview"></div></div></section>

  <section><div class="card" id="sec-index"><h2>指数行情 <small>开盘 / 收盘 / 成交额</small></h2>
    <div class="idx-grid" id="indices"></div></div></section>

  <section><div class="card"><h2>热点板块与题材 <small>按涨停数 / 涨跌幅排序</small></h2>
    <div id="blocks"></div></div></section>

  <section><div class="card"><h2>连板梯队 <small>题材 / 封板类型</small></h2>
    <div id="ladder"></div></div></section>

  <section><div class="card"><h2>龙虎榜 <small>买卖席位（机构 / 游资）</small></h2>
    <div id="lhb"></div></div></section>

  <section><div class="card"><h2>资金情况 <small>融资余额单位：亿元</small></h2>
    <div id="funds"></div></div></section>

  <section><div class="card"><h2>近 7 个交易日对比 <small>成交额单位：亿元 · 自建档日起累积</small></h2>
    <div id="history"></div></div></section>

  <section><div class="card"><h2>大宗商品走势 <small>近 60 个交易日</small></h2>
    <div id="charts"></div></div></section>

  <footer>
    数据来源：新浪财经 / 同花顺 / 东方财富<br>
    <span id="genTime"></span><br>
    本页仅供个人复盘参考，不构成投资建议
  </footer>
</div>

<script>
const DAYS = __DATA__;
const KL = __KLINE__;
const WEEK = ['周日','周一','周二','周三','周四','周五','周六'];

const $ = id => document.getElementById(id);
const isNum = v => (v !== null && v !== undefined && !isNaN(Number(v)));
const f = (v, d=2) => isNum(v) ? Number(v).toFixed(d) : '—';
const sg = (v, d=2) => isNum(v) ? (Number(v) > 0 ? '+' : '') + Number(v).toFixed(d) : '—';
const yi = v => isNum(v) ? (Number(v) / 1e8).toFixed(2) : '—';
const cls = v => (!isNum(v) || Number(v) === 0) ? 'flat' : (Number(v) > 0 ? 'up' : 'down');
const wan = v => isNum(v) ? (Number(v) / 1e4).toFixed(0) : '—';

function cmpHtml(cur, prev, unit, d=2){
  if(!isNum(cur) || !isNum(prev)) return '<span class="ov-cmp">（—）</span>';
  const dv = Number(cur) - Number(prev);
  const c = dv > 0 ? 'up' : (dv < 0 ? 'down' : 'flat');
  return `<span class="ov-cmp ${c}">（${sg(dv,d)}${unit||''}）</span>`;
}
function prevHtml(prev, unit, d=2){
  if(!isNum(prev)) return '<span class="ov-cmp">（昨 —）</span>';
  return `<span class="ov-cmp">（昨 ${Number(prev).toFixed(d)}${unit||''}）</span>`;
}
function dayOf(date){ return DAYS.find(d => d.date === date); }
function prevOf(date){
  const i = DAYS.findIndex(d => d.date === date);
  return i > 0 ? DAYS[i-1] : null;
}
function idxByName(day, name){
  if(!day || !day.indices) return null;
  return day.indices.find(x => x.name === name) || null;
}

/* ---------- 指数 ---------- */
function idxPart(it, label){
  if(!it){
    return `<div><div class="idx-lab flat">${label}</div>
      <div class="m">—</div></div>`;
  }
  const c = cls(it.change);   // 标签颜色跟随当日涨跌（红涨绿跌）
  return `<div><div class="idx-lab ${c}">${label}</div>
    <div class="m">开 ${f(it.open)}　收 ${f(it.close)}</div>
    <div class="m">成交额 ${it.amount_yi ? it.amount_yi + '亿' : '—'}</div>
  </div>`;
}
function renderIndices(day){
  const prev = prevOf(day.date);
  const list = (day.indices || []).filter(x => x.name !== '深证综指');
  $('indices').innerHTML = list.map(it => {
    const p = idxByName(prev, it.name);
    const c = cls(it.change);
    return `<div class="idx">
      <div class="n">${it.name}</div>
      <div class="c ${c}">${f(it.close)}</div>
      <div class="d ${c}">${sg(it.change)}　${sg(it.pct)}%</div>
      <div class="idx-split">
        ${idxPart(it, '今日')}
        ${idxPart(p, '上日')}
      </div>
    </div>`;
  }).join('') || '<div class="empty">暂无数据</div>';
}

/* ---------- 总览 ---------- */
function renderOverview(day){
  const prev = prevOf(day.date);
  const b = day.breadth, pb = prev ? prev.breadth : null;
  if(!b){ $('overview').innerHTML = '<div class="empty">暂无数据（当日未采集）</div>'; return; }

  const total = b.amount_total_yi;
  const pt = pb ? (isNum(pb.amount_total_yi) ? pb.amount_total_yi
    : (isNum(pb.amount_up_yi) && isNum(pb.amount_notup_yi) ? Number((pb.amount_up_yi + pb.amount_notup_yi).toFixed(2)) : null)) : null;
  const tw = b.up + b.down + b.flat;
  const pu = tw ? (b.up / tw * 100) : 0, pf = tw ? (b.flat / tw * 100) : 0, pd = tw ? (b.down / tw * 100) : 0;

  let h = '';
  h += `<div class="ov-row"><span class="ov-lab">三市成交额</span>
    <span><span class="ov-val">${isNum(total) ? total : '—'}</span>
    <span style="font-size:12px;color:var(--t3)">亿</span>${prevHtml(pt, '亿')}</span></div>`;

  if(isNum(b.amount_total_yi) && b.amount_yi){
    h += `<div style="padding:6px 0"><div class="kv">
      <div>沪市 <b>${b.amount_yi.sh}</b>亿</div>
      <div>深市 <b>${b.amount_yi.sz}</b>亿</div>
      <div>北交所 <b>${b.amount_yi.bj}</b>亿</div></div></div>`;
  }

  h += `<div style="margin-top:10px">
    <div class="bar">
      <i class="b-up" style="width:${pu}%"></i>
      <i class="b-flat" style="width:${pf}%"></i>
      <i class="b-down" style="width:${pd}%"></i>
    </div>
    <div class="legend">
      <span class="up">涨 <b>${b.up}</b>${prevHtml(pb && pb.up, '', 0)}</span>
      <span class="flat">平 <b>${b.flat}</b>${prevHtml(pb && pb.flat, '', 0)}</span>
      <span class="down">跌 <b>${b.down}</b>${prevHtml(pb && pb.down, '', 0)}</span>
    </div>
  </div>`;

  h += `<div style="display:flex;gap:10px;margin-top:12px">
    <div style="flex:1;border:1px solid var(--line);border-radius:10px;padding:9px">
      <div class="ov-lab">涨停</div>
      <div><span class="ov-val up">${b.limit_up}</span>${prevHtml(pb && pb.limit_up, '', 0)}</div>
    </div>
    <div style="flex:1;border:1px solid var(--line);border-radius:10px;padding:9px">
      <div class="ov-lab">跌停</div>
      <div><span class="ov-val down">${b.limit_down}</span>${prevHtml(pb && pb.limit_down, '', 0)}</div>
    </div>
  </div>`;

  if(pb && (!isNum(pb.amount_total_yi))){
    h += `<div class="hint">注：成交额为当日实时统计，历史成交额自建档起累积。</div>`;
  }
  $('overview').innerHTML = h;
}

/* ---------- 热点题材 ---------- */
let blockSort = 'lu';
window._lhbTab = 'buy';
function blocksTable(){
  const bs = (window._blocks || []).slice().sort((a, b) =>
    blockSort === 'lu' ? (b.limit_up_num || 0) - (a.limit_up_num || 0) : (b.pct || 0) - (a.pct || 0));
  if(!bs.length){ return '<div class="empty">暂无数据</div>'; }
  return `<table><thead><tr>
      <th>板块 / 题材</th><th class="num">涨跌幅</th><th class="num">涨停数</th><th>最高标</th></tr></thead><tbody>`
    + bs.map(b => {
      const st = (b.stocks || []).map(s => s.name).join('、');
      return `<tr>
        <td><b>${b.name}</b>${st ? `<div class="stk">${st}</div>` : ''}</td>
        <td class="num ${cls(b.pct)}">${sg(b.pct)}%</td>
        <td class="num">${b.limit_up_num ?? '—'}</td>
        <td style="font-size:12px">${b.top || '—'}</td></tr>`;
    }).join('') + '</tbody></table>';
}
function renderBlocks(day){
  window._blocks = (day.hot_blocks || []).slice(0, 15);
  $('blocks').innerHTML = `<div class="seg">
      <button data-k="lu" class="${blockSort==='lu'?'on':''}">按涨停数</button>
      <button data-k="pct" class="${blockSort==='pct'?'on':''}">按涨跌幅</button>
    </div><div id="blockTbl">${blocksTable()}</div>`;
  $('blocks').querySelectorAll('.seg button').forEach(btn => {
    btn.onclick = () => {
      blockSort = btn.dataset.k;
      $('blocks').querySelectorAll('.seg button').forEach(b2 =>
        b2.classList.toggle('on', b2 === btn));
      $('blockTbl').innerHTML = blocksTable();
    };
  });
}

/* ---------- 连板梯队 ---------- */
function renderLadder(day){
  const lp = day.limit_up_pool;
  if(!lp || !lp.ladder || !lp.ladder.length){ $('ladder').innerHTML = '<div class="empty">暂无数据</div>'; return; }
  let h = `<div style="font-size:13px;color:var(--t2);margin-bottom:10px">
    涨停 <b class="up">${lp.total}</b></div>`;
  h += lp.ladder.map(g => {
    const hot = g.level >= 3 ? ' hot' : '';
    return `<div class="lad">
      <div class="lad-h"><span class="lv${hot}">${g.label}</span>
        <span class="lad-c">${g.count} 只</span></div>
      <div class="chips">${g.stocks.map(s => `<span class="chip"><b>${s.name}</b>
        <span style="font-size:11px;color:var(--t3)"> ${s.code}</span>
        <span class="r">${(s.reason || s.board_type || '').slice(0,22)}</span></span>`).join('')}</div>
    </div>`;
  }).join('');
  $('ladder').innerHTML = h;
}

/* ---------- 龙虎榜 ---------- */
function seatTag(t){
  if(!t) return '';
  if(t.indexOf('机构') >= 0) return `<span class="inst">机构</span>`;
  if(t.indexOf('北向') >= 0) return `<span class="north">北向</span>`;
  return `<span class="yz">${t.replace('游资·','')}</span>`;
}
function seatRows(seats, kind){
  if(!seats || !seats.length) return '<div class="srow" style="color:var(--t3)">暂无</div>';
  return seats.map(s => `<div class="srow">
      <span class="sname">${s.name}${seatTag(s.tag)}</span>
      <span class="money ${kind === 'buy' ? 'up' : 'down'}">${wan(s.amount)}万</span></div>`).join('');
}
function latestLhb(){
  for(let i = DAYS.length - 1; i >= 0; i--){
    if(DAYS[i].lhb && DAYS[i].lhb.count) return DAYS[i];
  }
  return null;
}
function lhbItemHtml(it){
  const net = isNum(it.net) ? (it.net / 1e8) : null;
  return `<div class="lhb-item">
      <div class="lhb-h">
        <span class="lhb-n">${it.name} <span style="font-weight:400;font-size:12px;color:var(--t3)">${it.code}</span></span>
        <span style="display:flex;align-items:baseline;gap:8px">
          <span style="font-size:12px;color:var(--t3)">净买入 <b class="${cls(it.net)}" style="font-size:13px">${isNum(net) ? net.toFixed(2) + '亿' : '—'}</b></span>
          <span class="${cls(it.pct)}" style="font-weight:700">${sg(it.pct)}%</span>
          <span class="arr">▾</span>
        </span>
      </div>
      <div class="lhb-t">${it.reason || ''} · 收盘 ${f(it.close)} · 点开查看买卖席位</div>
      <div class="lhb-b"><div class="seats">
        <div class="seat-box"><h4>买入前五</h4>${seatRows(it.buy_seats, 'buy')}</div>
        <div class="seat-box"><h4>卖出前五</h4>${seatRows(it.sell_seats, 'sell')}</div>
      </div></div>
    </div>`;
}
function bindLhbToggle(root){
  (root || $('lhb')).querySelectorAll('.lhb-item').forEach(el => {
    el.onclick = () => el.classList.toggle('open');
  });
}
function lhbSorted(){
  const items = (window._lhb.lhb.items || []).slice();
  const v = x => (isNum(x.net) ? Number(x.net) : 0);
  return items.sort((a, b) => (window._lhbTab === 'buy' ? v(b) - v(a) : v(a) - v(b)));
}
function lhbListHtml(){
  const items = lhbSorted();
  let h = items.slice(0, 8).map(lhbItemHtml).join('');
  if(items.length > 8){
    h += `<button class="more" id="moreLhb">展开剩余 ${items.length - 8} 条 ▾</button><div id="rest"></div>`;
  }
  return h;
}
function renderLHB(day){
  const src = (day.lhb && day.lhb.count) ? day : latestLhb();
  if(!src){
    $('lhb').innerHTML = '<div class="empty">当日龙虎榜尚未公布（交易所一般收盘后发布）</div>';
    return;
  }
  window._lhb = src;
  const note = (src.date !== day.date)
    ? `<div style="font-size:12px;color:var(--t3);margin-bottom:8px">当日龙虎榜尚未公布，以下为最近一期（${src.date}）</div>` : '';
  $('lhb').innerHTML = note + `<div class="seg">
      <button data-k="buy" class="${window._lhbTab==='buy'?'on':''}">买入榜</button>
      <button data-k="sell" class="${window._lhbTab==='sell'?'on':''}">卖出榜</button>
    </div><div id="lhbList">${lhbListHtml()}</div>`;
  $('lhb').querySelectorAll('.seg button').forEach(btn => {
    btn.onclick = () => {
      window._lhbTab = btn.dataset.k;
      $('lhb').querySelectorAll('.seg button').forEach(b2 => b2.classList.toggle('on', b2 === btn));
      $('lhbList').innerHTML = lhbListHtml();
      bindLhbToggle($('lhbList'));
    };
  });
  bindLhbToggle($('lhbList'));
  const btn = $('moreLhb');
  if(btn){
    btn.onclick = e => {
      e.stopPropagation();
      $('rest').innerHTML = lhbSorted().slice(8).map(lhbItemHtml).join('');
      btn.style.display = 'none';
      bindLhbToggle($('rest'));
    };
  }
}

/* ---------- 商品走势 ---------- */
function drawChart(points, color, unit){
  if(!points || points.length < 2) return '<div class="empty">暂无数据</div>';
  const W = 700, H = 130, PL = 8, PR = 8, PT = 12, PB = 18;
  const vals = points.map(p => p.close);
  const mn = Math.min(...vals), mx = Math.max(...vals);
  const span = (mx - mn) || 1;
  const x = i => PL + i * (W - PL - PR) / (points.length - 1);
  const y = v => PT + (1 - (v - mn) / span) * (H - PT - PB);
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.close).toFixed(1)}`).join(' ');
  const area = `${line} L${x(points.length-1).toFixed(1)},${H-PB} L${x(0).toFixed(1)},${H-PB} Z`;
  const last = points[points.length - 1], first = points[0];
  const chg = (last.close / first.close - 1) * 100;
  const gid = 'g' + Math.random().toString(36).slice(2, 8);
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity=".26"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <path d="${area}" fill="url(#${gid})"/>
    <path d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${x(points.length-1).toFixed(1)}" cy="${y(last.close).toFixed(1)}" r="3.5" fill="${color}"/>
  </svg>`;
}
function chartBlock(title, points, color, unit){
  if(!points || !points.length) return `<div class="chart-box"><div class="chart-hd"><span class="t">${title}</span></div></div>`;
  const last = points[points.length - 1], first = points[0];
  const chg = (last.close / first.close - 1) * 100;
  return `<div class="chart-box">
    <div class="chart-hd">
      <span class="t">${title}</span>
      <span><span class="v">${f(last.close)}</span>
        <span class="c ${cls(chg)}">${sg(chg)}%</span></span>
    </div>
    ${drawChart(points, color)}
    <div class="stk" style="display:flex;justify-content:space-between">
      <span>${points[0].date}</span>
      <span>区间 ${f(Math.min(...points.map(p=>p.close)))} ~ ${f(Math.max(...points.map(p=>p.close)))} ${unit}</span>
      <span>${last.date}</span>
    </div>
  </div>`;
}
function renderCharts(day){
  const c = day.commodities || {};
  $('charts').innerHTML = chartBlock('布伦特原油（美元/桶）', c.brent, '#c9922e', '美元')
    + '<div style="height:14px"></div>'
    + chartBlock('纽约黄金（美元/盎司）', c.gold, '#d4a017', '美元');
}

/* ---------- 资金情况 ---------- */
function fundCard(title, val, unit, sub){
  return `<div style="flex:1;min-width:0;border:1px solid var(--line);border-radius:10px;padding:9px 8px">
    <div class="ov-lab">${title}</div>
    <div class="ov-val" style="white-space:nowrap;font-size:16px">${isNum(val) ? val : '—'}<span style="font-size:11px;color:var(--t3);font-weight:400;margin-left:2px">${unit||''}</span></div>
    <div style="font-size:10px;color:var(--t3);margin-top:2px;white-space:nowrap">${sub || ''}</div>
  </div>`;
}
function renderFunds(day){
  const src = (day.funds && (day.funds.margin || day.funds.north)) ? day : null;
  const alt = src ? null : (function(){
    for(let i = DAYS.length - 1; i >= 0; i--){
      if(DAYS[i].funds && (DAYS[i].funds.margin || DAYS[i].funds.north)) return DAYS[i];
    }
    return null;
  })();
  const s = src || alt;
  if(!s){ $('funds').innerHTML = '<div class="empty">暂无数据</div>'; return; }
  const m = (s.funds || {}).margin || {};
  const n = (s.funds || {}).north || {};
  const mdate = m.date || n.date || s.date;   // 按数据实际所属日期提示，而不是文件所在日
  const note = (mdate !== day.date)
    ? `<div style="font-size:12px;color:var(--t3);margin-bottom:8px">融资/北向数据为 T+1 披露，以下为最新一期（${mdate}）</div>` : '';
  const chg = isNum(m.fin_chg) ? `<span class="${cls(m.fin_chg)}">${sg(m.fin_chg)}亿</span>` : '—';
  $('funds').innerHTML = note + `<div style="display:flex;gap:10px">
    ${fundCard('北向成交额', n.deal_amt, '亿', n.deal_amt ? '沪股通+深股通' : '暂无')}
    ${fundCard('融资余额', m.fin_balance, '亿', '较上日 ' + chg)}
    ${fundCard('两融余额', m.margin_balance, '亿', isNum(m.fin_buy_amt) ? '融资买入 ' + m.fin_buy_amt + '亿' : '')}
  </div>`;
}

/* ---------- 近7个交易日对比 ---------- */
function renderHistory(day){
  let rows = (KL || []).filter(k => k.date <= day.date).slice(-7);
  // 当天为盘中实时数据，日K线里还没有，补在最后一行
  if(day && !rows.some(k => k.date === day.date)){
    const sh = idxByName(day, '上证指数');
    if(sh) rows = rows.concat([{date: day.date, close: sh.close, pct: sh.pct}]).slice(-7);
  }
  if(!rows.length){ $('history').innerHTML = '<div class="empty">暂无数据</div>'; return; }
  let h = `<div class="hwrap" id="hw"><table class="htable"><thead><tr>
    <th>日期</th><th class="num">上证收盘</th><th class="num">涨跌幅</th>
    <th class="num">三市成交额</th><th class="num">涨/非涨额比</th>
    <th class="num">涨 / 跌</th><th class="num">涨/跌停</th></tr></thead><tbody>`;
  rows.forEach(k => {
    const d = dayOf(k.date);
    const b = d && d.breadth;
    const amt = b ? b.amount_total_yi : null;
    const todayRow = k.date === day.date;
    h += `<tr${todayRow ? ' class="today"' : ''}>
      <td class="date">${k.date.slice(5)}${todayRow ? ' <span style="color:var(--blue);font-size:11px">今日' +
        (day.updated_at ? ' 截至 ' + day.updated_at.slice(11,16) : '') + '</span>' : ''}</td>
      <td class="num">${f(k.close)}</td>
      <td class="num ${cls(k.pct)}">${sg(k.pct)}%</td>
      <td class="num">${isNum(amt) ? amt : '—'}</td>
      <td class="num">${b && isNum(b.up_notup_ratio) ? `<span class="frac-up">${b.up_notup_ratio}</span>` : '—'}</td>
      <td class="num">${b ? `<span class="frac-up">${b.up}</span>/<span class="frac-down">${b.down}</span>` : '—'}</td>
      <td class="num">${b ? `<span class="frac-up">${b.limit_up}</span>/<span class="frac-down">${b.limit_down}</span>` : '—'}</td>
    </tr>`;
  });
  h += '</tbody></table></div><div class="hbar" id="hscroll"><i></i></div>';
  $('history').innerHTML = h;
  // 横向滚动进度滑块
  const wrap = $('hw'), bar = $('hscroll'), thumb = bar.querySelector('i');
  const upd = () => {
    const vis = wrap.clientWidth, all = wrap.scrollWidth;
    if(all <= vis + 1){ bar.style.display = 'none'; return; }
    bar.style.display = 'block';
    const w = Math.max(28, vis / all * bar.clientWidth);
    thumb.style.width = w + 'px';
    thumb.style.left = (wrap.scrollLeft / (all - vis)) * (bar.clientWidth - w) + 'px';
  };
  wrap.addEventListener('scroll', upd, {passive: true});
  wrap.addEventListener('touchmove', upd, {passive: true});
  window.addEventListener('resize', upd);
  upd();
}

/* ---------- 头部状态 ---------- */
function renderStatus(day){
  const s = [];
  s.push(`<span class="badge">行情 · ${day.updated_at || '—'}</span>`);
  if(day.realtime === false) s.push(`<span class="badge">收盘数据</span>`);
  // 龙虎榜徽章：统一显示 当前展示数据的日期 + 抓取时刻（不显示条数）
  let lday = null;
  if(day.lhb && day.lhb.count) lday = day;
  else for(let i = DAYS.length - 1; i >= 0; i--){ if(DAYS[i].lhb && DAYS[i].lhb.count){ lday = DAYS[i]; break; } }
  // 徽章显示：数据所属日期 + 该期龙虎榜的抓取时刻
  const lt = (lday && lday.lhb_updated_at) ? lday.lhb_updated_at.slice(11) : '';
  s.push(lday ? `<span class="badge">龙虎榜 · ${lday.date}${lt ? ' ' + lt : ''}</span>`
              : `<span class="badge warn">龙虎榜待更新</span>`);
  $('status').innerHTML = s.join('');
}

/* ---------- 主渲染 ---------- */
function render(date){
  const day = dayOf(date);
  if(!day) return;
  $('dateSel').value = date;
  renderStatus(day);
  renderIndices(day);
  renderOverview(day);
  renderBlocks(day);
  renderLadder(day);
  renderLHB(day);
  renderFunds(day);
  renderHistory(day);
  renderCharts(day);
  $('genTime').textContent = '页面生成：__GEN__　共收录 ' + DAYS.length + ' 个交易日';
}

function init(){
  const sel = $('dateSel');
  sel.innerHTML = DAYS.slice().reverse().map(d =>
    `<option value="${d.date}">${d.date} ${WEEK[new Date(d.date.replace(/-/g,'/')).getDay()]}</option>`).join('');
  sel.onchange = e => render(e.target.value);
  $('prev').onclick = () => {
    const i = DAYS.findIndex(d => d.date === sel.value);
    if(i > 0) render(DAYS[i-1].date);          // 左箭头：往前一天（更早）
  };
  $('next').onclick = () => {
    const i = DAYS.findIndex(d => d.date === sel.value);
    if(i < DAYS.length - 1) render(DAYS[i+1].date);  // 右箭头：往后一天（更晚）
  };
  render(DAYS[DAYS.length - 1].date);
}
init();
</script>
</body>
</html>
"""


def fetch_sh_kline(n=15):
    """上证指数近 n 个交易日日K，用于'近7个交易日对比'"""
    import requests
    url = ('https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           'CN_MarketData.getKLineData?symbol=sh000001&scale=240&ma=no&datalen=%d' % n)
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0',
                                       'Referer': 'https://finance.sina.com.cn'}, timeout=20)
        ks = r.json()
    except Exception:
        return []
    out = []
    for i, k in enumerate(ks):
        try:
            close = float(k['close'])
            pct = None
            if i > 0:
                pct = round((close / float(ks[i - 1]['close']) - 1) * 100, 2)
            out.append({'date': k['day'], 'close': close, 'pct': pct})
        except (KeyError, ValueError, TypeError):
            continue
    return out


def main():
    days = load_days()
    if not days:
        print('[error] data/ 下没有数据')
        return
    kline = fetch_sh_kline(15)
    last_date = days[-1]['date']
    kline = [k for k in kline if k['date'] <= last_date]
    data_json = json.dumps(days, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    kl_json = json.dumps(kline, ensure_ascii=False, separators=(',', ':'))
    gen = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    html = (HTML.replace('__DATA__', data_json)
                .replace('__KLINE__', kl_json)
                .replace('__GEN__', gen))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('[build] -> %s  (%d 个交易日, %d 条K线, %.1f KB)'
          % (OUT, len(days), len(kline), len(html) / 1024))


if __name__ == '__main__':
    main()
