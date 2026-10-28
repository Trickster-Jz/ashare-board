#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股每日复盘看板 - 数据抓取脚本

阶段说明：
  market   交易日下午16:00 执行  -> 指数/家数/成交额/涨停梯队/热点题材/商品走势
  lhb      交易日下午19:00 执行  -> 龙虎榜明细（含买卖席位、游资识别）
  backfill 补历史某日的涨跌家数/涨跌停家数（用个股日K批量回溯，较慢，仅补数据时用）

用法：
  python3 fetch_data.py --stage market
  python3 fetch_data.py --stage market --date 2026-10-23
  python3 fetch_data.py --stage lhb    --date 2026-10-23
  python3 fetch_data.py --stage backfill --date 2026-10-23
"""

import argparse
import json
import os
import re
import sys
import time
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1')
BASE_HEADERS = {'User-Agent': UA}
SINA_REFERER = {'Referer': 'https://finance.sina.com.cn'}


def get(url, headers=None, timeout=25, retries=3, encoding=None):
    h = dict(BASE_HEADERS)
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=h, timeout=timeout)
            if encoding:
                r.encoding = encoding
            return r
        except Exception as e:  # noqa
            last = e
            time.sleep(1.2 * (i + 1))
    raise last


def get_json(url, headers=None, timeout=25, retries=3, encoding=None):
    r = get(url, headers=headers, timeout=timeout, retries=retries, encoding=encoding)
    return r.json()


# ---------------------------------------------------------------- 工具

def today_str():
    return dt.date.today().strftime('%Y-%m-%d')


def load_day(date_str):
    p = os.path.join(DATA_DIR, date_str + '.json')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_day(date_str, data):
    p = os.path.join(DATA_DIR, date_str + '.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return p


def upsert_day(date_str, patch):
    d = load_day(date_str) or {'date': date_str}
    for k, v in patch.items():
        d[k] = v
    d['date'] = date_str
    d['updated_at'] = now_bj()
    save_day(date_str, d)
    return d


def limit_pct(symbol, name):
    """返回该股票的涨跌停幅度(%)"""
    code = symbol[2:]
    n = str(name).upper().replace(' ', '')
    is_st = ('ST' in n) or ('退' in n)
    if symbol.startswith('bj'):        # 北交所 30%
        return 30.0
    if code.startswith(('300', '301', '688', '689')):   # 创业板/科创板 20%
        return 20.0
    if is_st:
        return 5.0
    return 10.0


def market_of(symbol):
    if symbol.startswith('sh'):
        return 'sh'
    if symbol.startswith('sz'):
        return 'sz'
    if symbol.startswith('bj'):
        return 'bj'
    return 'other'


def fmt_amount(yuan):
    """元 -> 亿元"""
    return round(yuan / 1e8, 2) if yuan else None


# ---------------------------------------------------------------- 指数

INDEX_LIST = [
    ('sh000001', '上证指数'),
    ('sz399001', '深证成指'),
    ('sz399006', '创业板指'),
    ('sh000688', '科创50'),
    ('bj899050', '北证50'),
    ('sh000300', '沪深300'),
]

# 用于计算三市成交额的"全市场指数"（综指覆盖全部个股）
TURNOVER_INDEX = {'sh': 'sh000001', 'sz': 'sz399106', 'bj': 'bj899050'}


def fetch_indices_realtime():
    """实时/收盘行情（新浪指数接口）"""
    codes = [c for c, _ in INDEX_LIST] + ['sz399106']
    url = 'https://hq.sinajs.cn/list=' + ','.join(codes)
    r = get(url, headers=SINA_REFERER, encoding='gbk')
    out = {}
    for line in r.text.split(';'):
        line = line.strip()
        m = re.match(r'var hq_str_(\w+)="(.*)"', line)
        if not m:
            continue
        code, body = m.group(1), m.group(2)
        f = body.split(',')
        if len(f) < 10:
            continue
        try:
            item = {
                'code': code,
                'name': f[0],
                'open': float(f[1]),
                'prev_close': float(f[2]),
                'close': float(f[3]),
                'high': float(f[4]),
                'low': float(f[5]),
                'amount': float(f[9]) if f[9] else None,   # 元
            }
        except ValueError:
            continue
        item['change'] = round(item['close'] - item['prev_close'], 2)
        item['pct'] = round((item['close'] / item['prev_close'] - 1) * 100, 2) if item['prev_close'] else 0.0
        item['amount_yi'] = fmt_amount(item['amount'])
        qdate = None
        for fld in reversed(f):
            if re.match(r'^\d{4}-\d{2}-\d{2}$', fld):
                qdate = fld
                break
        item['quote_date'] = qdate
        out[code] = item
    return out


def is_trading_day(indices):
    """用上证指数行情自带的日期判断今天是否交易日（节假日自动跳过）"""
    it = indices.get('sh000001')
    if not it:
        return True
    return it.get('quote_date') == today_str()


def fetch_index_kline(symbol, datalen=10):
    """指数日K，用于历史日期回溯"""
    url = ('https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           'CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=%d' % (symbol, datalen))
    r = get(url, headers=SINA_REFERER)
    txt = r.text.strip()
    try:
        return json.loads(txt)
    except Exception:
        return []


def indices_for_date(date_str):
    """取指定日期的指数行情：当日实时 or 历史K线"""
    if date_str == today_str():
        return fetch_indices_realtime(), True
    want = date_str
    res = {}
    for code, name in INDEX_LIST:
        ks = fetch_index_kline(code, datalen=10)
        hit = None
        prev = None
        for i, k in enumerate(ks):
            if k['day'] == want:
                hit = k
                prev = ks[i - 1] if i > 0 else None
                break
        if not hit:
            continue
        prev_close = float(prev['close']) if prev else None
        close = float(hit['close'])
        res[code] = {
            'code': code, 'name': name,
            'open': float(hit['open']), 'high': float(hit['high']), 'low': float(hit['low']),
            'close': close, 'prev_close': prev_close,
            'change': round(close - prev_close, 2) if prev_close else None,
            'pct': round((close / prev_close - 1) * 100, 2) if prev_close else None,
            'amount': None, 'amount_yi': None,
        }
    return res, False


# ---------------------------------------------------------------- 全市场个股

STOCK_COUNT_URL = ('https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
                   'Market_Center.getHQNodeStockCount?node=hs_a')
STOCK_LIST_URL = ('https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
                  'Market_Center.getHQNodeData?page=%d&num=100&sort=symbol&asc=1&node=hs_a&_s_r_a=page')


def fetch_all_stocks(max_workers=8):
    """抓取全部A股（含北交所）当日快照"""
    total = 5576
    try:
        r = get(STOCK_COUNT_URL, headers=SINA_REFERER)
        total = int(json.loads(r.text))
    except Exception:
        pass
    pages = (total // 100) + 2

    def one(page):
        try:
            r = get(STOCK_LIST_URL % page, headers=SINA_REFERER, timeout=25)
            txt = r.text.strip()
            if not txt or txt in ('null', '[]'):
                return []
            return json.loads(txt)
        except Exception:
            return []

    stocks = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(one, p) for p in range(1, pages)]
        for fu in as_completed(futs):
            stocks.extend(fu.result() or [])

    # 去重
    seen, uniq = set(), []
    for s in stocks:
        sym = s.get('symbol')
        if sym and sym not in seen:
            seen.add(sym)
            uniq.append(s)
    return uniq


def summarize_stocks(stocks):
    """统计涨跌家数、涨跌停家数、三市成交额"""
    up = down = flat = 0
    lu = ld = 0
    amount = {'sh': 0.0, 'sz': 0.0, 'bj': 0.0}
    amt_up = 0.0          # 上涨股票成交额
    amt_down = 0.0        # 下跌股票成交额
    amt_notup = 0.0       # 非上涨（平+跌）股票成交额
    lu_list, ld_list = [], []
    for s in stocks:
        sym = s.get('symbol', '')
        name = s.get('name', '')
        try:
            pct = float(s.get('changepercent') or 0)
            price = float(s.get('trade') or 0)
            high = float(s.get('high') or 0)
            low = float(s.get('low') or 0)
            amt = float(s.get('amount') or 0)
        except (TypeError, ValueError):
            continue
        if pct > 0:
            up += 1
        elif pct < 0:
            down += 1
        else:
            flat += 1
        m = market_of(sym)
        amount[m] += amt
        if pct > 0:
            amt_up += amt
        elif pct < 0:
            amt_down += amt
            amt_notup += amt
        else:
            amt_notup += amt
        lim = limit_pct(sym, name)
        if price > 0:
            if pct >= lim - 0.35 and high > 0 and price >= high * 0.9995:
                lu += 1
                lu_list.append({'symbol': sym, 'code': s.get('code'), 'name': name, 'pct': pct})
            elif pct <= -(lim - 0.35) and low > 0 and price <= low * 1.0005:
                ld += 1
                ld_list.append({'symbol': sym, 'code': s.get('code'), 'name': name, 'pct': pct})
    return {
        'up': up, 'down': down, 'flat': flat,
        'limit_up': lu, 'limit_down': ld,
        'total': up + down + flat,
        'amount_yi': {k: fmt_amount(v) for k, v in amount.items()},
        'amount_total_yi': fmt_amount(sum(amount.values())),
        'amount_up_yi': fmt_amount(amt_up),
        'amount_down_yi': fmt_amount(amt_down),
        'amount_notup_yi': fmt_amount(amt_notup),
        'up_notup_ratio': round(amt_up / amt_notup, 2) if amt_notup else None,
        'limit_up_list': lu_list,
        'limit_down_list': ld_list,
    }


# ---------------------------------------------------------------- 涨停池 / 连板梯队 / 热点题材

THS_LIMIT_FIELDS = ('199112,10,9001,330323,330324,330325,9002,330329,133971,133970,'
                    '1968584,3475914,9003,9004')


def fetch_limit_pool(date_compact, page_size=100):
    """同花顺涨停池。带 filter 时盘中可能暂无数据，失败则回退不带 filter 的请求。"""
    base = ('https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool?'
            'page=1&limit=%d&field=%s&order_field=330324&order_type=0&date=%s')
    for suffix in ('&filter=HS,GEM2STAR', ''):
        url = base % (page_size, THS_LIMIT_FIELDS, date_compact) + suffix
        try:
            js = get(url, headers={'Referer': 'https://data.10jqka.com.cn/'}).json()
            info = (js.get('data') or {}).get('info') or []
            if info:
                return js
        except Exception:
            continue
    return {}


def parse_ladder(info):
    """把涨停池整理成连板梯队"""
    def level_of(it):
        hd = str(it.get('high_days') or '首板')
        m = re.search(r'(\d+)板', hd)
        if m:
            return int(m.group(1))
        if '首板' in hd:
            return 1
        return 1

    groups = {}
    for it in info:
        lv = level_of(it)
        groups.setdefault(lv, []).append({
            'code': it.get('code'),
            'name': it.get('name'),
            'pct': it.get('change_rate'),
            'price': it.get('latest'),
            'board_type': it.get('limit_up_type'),
            'reason': it.get('reason_type') or '',
            'turnover': it.get('turnover_rate'),
            'open_num': it.get('open_num'),
            'seal_amount': it.get('order_amount'),   # 封单额(万元)
            'luv': it.get('currency_value'),         # 流通市值(元)
        })
    ladder = []
    for lv in sorted(groups.keys(), reverse=True):
        ladder.append({'level': lv, 'label': ('首板' if lv == 1 else '%d板' % lv),
                       'count': len(groups[lv]), 'stocks': groups[lv][:12]})
    return ladder


def fetch_hot_blocks(date_compact, limit=12):
    """同花顺涨停板块榜 -> 热点题材"""
    url = ('https://data.10jqka.com.cn/dataapi/limit_up/block_top?date=%s&limit=%d'
           % (date_compact, limit))
    r = get(url, headers={'Referer': 'https://data.10jqka.com.cn/'})
    try:
        js = r.json()
    except Exception:
        return []
    out = []
    for b in (js.get('data') or []):
        stocks = []
        # 涨停股全量保存（可点开查看），上限 60 只保护
        # 注意：板块接口的 high_days 是数字位编码（与涨停池接口同名不同义），不采集
        for s in (b.get('stock_list') or [])[:60]:
            stocks.append({'code': s.get('code'), 'name': s.get('name')})
        out.append({
            'name': b.get('name'),
            'pct': b.get('change'),
            'limit_up_num': b.get('limit_up_num'),
            'continuous': b.get('continuous_plate_num'),
            'top': b.get('high'),
            'days': b.get('days'),
            'stocks': stocks,
        })
    return out


# ---------------------------------------------------------------- 龙虎榜

EM_DC = 'https://datacenter-web.eastmoney.com/api/data/v1/get'

# 知名游资 / 机构席位映射（按营业部名称关键词）
SEAT_MAP = [
    (['拉萨', '东方财富'], '拉萨天团(散户)'),
    (['机构专用'], '机构专用'),
    (['深股通', '沪股通', '港股通', '香港中央结算'], '北向资金'),
    (['摩根大通', '瑞银', '高盛', '野村', '摩根士丹利', '美林', '法国巴黎', '汇丰'], '外资席位'),
    (['上海江苏路', '溧阳路'], '章盟主'),
    (['绍兴'], '赵老哥'),
    (['佛山绿景', '佛山季华'], '佛山无影脚'),
    (['茅台路', '上海分公司', '华鑫证券有限责任公司上海'], '炒股养家'),
    (['南京太平南路'], '作手新一'),
    (['宁波桑田路'], '宁波桑田路'),
    (['成都北一环', '成都蜀金', '成都天府'], '成都帮'),
    (['金田路'], '金田路'),
    (['民田路', '益田路荣超'], '欢乐海岸'),
    (['朱雀大街', '陕西分公司'], '方新侠'),
    (['厦门厦禾路'], '厦门帮'),
    (['杭州四季路', '杭州庆春路'], '杭州帮'),
    (['台州', '温岭'], '台州帮'),
    (['深圳蛇口', '深圳益田'], '深圳帮'),
    (['上海牡丹江路'], '量化席位'),
    (['上海花园石桥', '上海世纪大道'], '量化/机构'),
    # 常见知名游资席位（以营业部/路段特征标注）
    (['三亚迎宾路'], '游资·三亚迎宾路'),
    (['西安西大街', '西安朱雀大街', '陕西分公司'], '游资·西安系'),
    (['中山东路'], '游资·松江中山东路'),
    (['杨树浦路'], '游资·杨树浦路'),
    (['中关村大街'], '游资·中关村'),
    (['萧山市心中路', '杭州萧山'], '游资·杭州帮'),
    (['深圳后海', '深圳科技园'], '游资·深圳系'),
    (['苏州星海街', '苏州苏绣路'], '游资·苏州系'),
    (['南京太平南路'], '游资·作手新一'),
    (['上海分公司', '上海自贸区'], '游资/量化'),
]


def seat_tag(name):
    n = str(name or '')
    for keys, tag in SEAT_MAP:
        for k in keys:
            if k in n:
                return tag
    return None


def short_seat(name):
    """营业部冗长名称 -> 简短显示"""
    n = str(name or '').replace('证券股份有限公司', '').replace('股份有限公司', '').replace('有限责任公司', '')
    return n.strip()


def now_bj():
    """北京时间时间戳（服务器可能为 UTC，统一按 UTC+8 输出）"""
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')


def fetch_lhb(date_str):
    """龙虎榜：榜单 + 买卖席位"""
    filt = "(TRADE_DATE='%s')" % date_str
    list_url = (EM_DC + '?reportName=RPT_DAILYBILLBOARD_DETAILSNEW&columns=ALL&pageSize=100&pageNumber=1'
                '&sortColumns=BILLBOARD_NET_AMT&sortTypes=-1&filter=' + requests.utils.quote(filt))
    rows = []
    try:
        js = get_json(list_url)
        rows = ((js.get('result') or {}).get('data') or [])
    except Exception as e:
        print('[warn] lhb list fail: %s' % e, file=sys.stderr)

    # 席位明细
    seats = {}
    for rep in ('RPT_BILLBOARD_DAILYDETAILSBUY', 'RPT_BILLBOARD_DAILYDETAILSSELL'):
        u = (EM_DC + '?reportName=%s&columns=ALL&pageSize=500&pageNumber=1'
             '&sortColumns=BUY,BUY&sortTypes=-1,-1&filter=' % rep) + requests.utils.quote(filt)
        try:
            js = get_json(u)
            for d in ((js.get('result') or {}).get('data') or []):
                code = d.get('SECURITY_CODE')
                if not code:
                    continue
                rec = seats.setdefault(code, {'buy': [], 'sell': []})
                nm = d.get('OPERATEDEPT_NAME')
                if not nm:
                    continue
                tag = seat_tag(nm)
                if rep.endswith('BUY') and d.get('BUY'):
                    rec['buy'].append({'name': short_seat(nm), 'full': nm, 'tag': tag,
                                       'amount': d.get('BUY')})
                elif rep.endswith('SELL') and d.get('SELL'):
                    rec['sell'].append({'name': short_seat(nm), 'full': nm, 'tag': tag,
                                        'amount': d.get('SELL')})
        except Exception as e:
            print('[warn] %s fail: %s' % (rep, e), file=sys.stderr)

    items = []
    # 去重：同一股票可能因多个上榜原因出现多条，只保留 |净买卖额| 最大的一条，
    # 上榜原因合并展示，避免重复股票且不同口径数据对不上
    best, reasons = {}, {}
    for r in rows:
        code = r.get('SECURITY_CODE')
        if not code:
            continue
        b = best.get(code)
        if b is None or abs(r.get('BILLBOARD_NET_AMT') or 0) > abs(b.get('BILLBOARD_NET_AMT') or 0):
            best[code] = r
        ex = (r.get('EXPLANATION') or r.get('EXPLAIN') or '').strip()
        if ex and ex not in reasons.get(code, []):
            reasons.setdefault(code, []).append(ex)

    for code, r in best.items():
        s = seats.get(code, {'buy': [], 'sell': []})

        def _dedup(lst):
            seen, out = set(), []
            for x in lst:
                k = (x['name'], x['amount'])
                if k in seen:
                    continue
                seen.add(k)
                out.append(x)
            return out

        s['buy'] = sorted(_dedup(s['buy']), key=lambda x: -(x['amount'] or 0))[:5]
        s['sell'] = sorted(_dedup(s['sell']), key=lambda x: -(x['amount'] or 0))[:5]
        items.append({
            'code': code,
            'name': r.get('SECURITY_NAME_ABBR'),
            'close': r.get('CLOSE_PRICE'),
            'pct': round(r.get('CHANGE_RATE'), 2) if r.get('CHANGE_RATE') is not None else None,
            'net': r.get('BILLBOARD_NET_AMT'),          # 净买入(元)
            'buy_total': r.get('BILLBOARD_BUY_AMT'),
            'sell_total': r.get('BILLBOARD_SELL_AMT'),
            'deal': r.get('BILLBOARD_DEAL_AMT'),
            'turnover': r.get('TURNOVERRATE'),
            'reason': '；'.join(reasons.get(code, [])),
            'buy_seats': s['buy'],
            'sell_seats': s['sell'],
        })
    items.sort(key=lambda x: -(x['net'] or 0))
    return {'count': len(items), 'items': items}


# ---------------------------------------------------------------- 资金情况

def fetch_funds(date_str):
    """融资余额（两融）+ 北向成交额"""
    out = {'margin': None, 'north': None}
    # 融资融券（东财 datacenter，单位：亿元）
    try:
        u = (EM_DC + '?reportName=RPTA_WEB_MARGIN_DAILYTRADE&columns=ALL&pageSize=8&pageNumber=1'
             '&sortColumns=STATISTICS_DATE&sortTypes=-1&filter='
             + requests.utils.quote("(STATISTICS_DATE<='%s')" % date_str))
        rows = ((get_json(u).get('result') or {}).get('data') or [])
        cur = rows[0] if rows else None            # 融资余额 T+1 披露，取最新可得一期
        prev = rows[1] if len(rows) > 1 else None
        if cur:
            fb, mb, fbuy = cur.get('FIN_BALANCE'), cur.get('MARGIN_BALANCE'), cur.get('FIN_BUY_AMT')
            pfb = prev.get('FIN_BALANCE') if prev else None
            out['margin'] = {
                'date': (cur.get('STATISTICS_DATE') or '')[:10],
                'fin_balance': round(fb, 2) if fb else None,          # 融资余额(亿)
                'margin_balance': round(mb, 2) if mb else None,       # 两融余额(亿)
                'fin_buy_amt': round(fbuy, 2) if fbuy else None,      # 融资买入额(亿)
                'fin_chg': round(fb - pfb, 2) if (fb and pfb) else None,
            }
    except Exception as e:
        print('[warn] margin fail: %s' % e, file=sys.stderr)

    # 北向（沪股通+深股通）成交总额，单位：百万元 -> 亿元
    try:
        u = (EM_DC + '?reportName=RPT_MUTUAL_DEAL_HISTORY&columns=ALL&pageSize=30&pageNumber=1'
             '&sortColumns=TRADE_DATE&sortTypes=-1&filter='
             + requests.utils.quote("(TRADE_DATE<='%s')" % date_str))
        rows = ((get_json(u).get('result') or {}).get('data') or [])
        if rows:
            latest = (rows[0].get('TRADE_DATE') or '')[:10]
            tot = 0.0
            for r in rows:
                if (r.get('TRADE_DATE') or '')[:10] != latest:
                    continue
                if str(r.get('MUTUAL_TYPE')) in ('001', '003') and r.get('DEAL_AMT'):
                    tot += float(r['DEAL_AMT'])
            if tot:
                # 净流入已停止披露，只取成交额
                out['north'] = {'deal_amt': round(tot / 100, 2), 'net': None, 'date': latest}
    except Exception as e:
        print('[warn] north fail: %s' % e, file=sys.stderr)
    return out


# ---------------------------------------------------------------- 商品走势

def fetch_sp500(days=90):
    """新浪美股指数日K：.INX = 标普500"""
    url = ('https://stock.finance.sina.com.cn/usstock/api/json_v2.php/'
           'US_MinKService.getDailyK?symbol=.INX')
    r = get(url, headers=SINA_REFERER, timeout=30)
    try:
        arr = json.loads(r.text)
    except Exception:
        return []
    out = []
    for k in arr:
        try:
            out.append({'date': k['d'], 'close': float(k['c'])})
        except (KeyError, ValueError):
            continue
    return out[-days:]


def fetch_commodity(symbol, days=90):
    """新浪外盘期货日K：OIL=布伦特原油, GC=纽约黄金"""
    url = ('https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%%20_%s=/'
           'GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=%s' % (symbol, symbol))
    r = get(url, headers=SINA_REFERER, timeout=30)
    m = re.search(r'=\s*\((\[.*\])\)', r.text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(1))
    except Exception:
        return []
    out = []
    for k in arr:
        try:
            out.append({'date': k['date'], 'close': float(k['close'])})
        except (KeyError, ValueError):
            continue
    return out[-days:]


# ---------------------------------------------------------------- 历史回溯（涨跌家数）

def backfill_breadth(date_str, max_workers=12):
    """用个股日K批量回溯某日的涨跌/涨跌停家数（较慢，用于补历史）"""
    cache_path = os.path.join(CACHE_DIR, 'stock_meta.json')
    meta = []
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    if not meta:
        print('[info] 无股票名册缓存，先抓全市场快照...')
        stocks = fetch_all_stocks()
        meta = [{'symbol': s['symbol'], 'code': s['code'], 'name': s['name']} for s in stocks]
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)

    print('[info] 回溯 %s，共 %d 只个股...' % (date_str, len(meta)))
    up = down = flat = 0
    lu = ld = 0
    amt_up = amt_down = amt_notup = 0.0
    done = [0]

    def one(m):
        ks = fetch_index_kline(m['symbol'], datalen=8)
        if len(ks) < 2:
            return None
        prev_close = None
        cur = None
        for i, k in enumerate(ks):
            if k['day'] == date_str:
                cur = k
                prev_close = float(ks[i - 1]['close']) if i > 0 else None
                break
        if not cur or not prev_close:
            return None
        close = float(cur['close'])
        pct = (close / prev_close - 1) * 100
        lim = limit_pct(m['symbol'], m['name'])
        is_lu = pct >= lim - 0.35 and close >= float(cur['high']) * 0.9995
        is_ld = pct <= -(lim - 0.35) and close <= float(cur['low']) * 1.0005
        # 日K无成交额，用 成交量×收盘价 估算（误差约 1%~3%，用于计算涨跌分组成交额比值）
        try:
            amt = float(cur['volume']) * close
        except (KeyError, ValueError, TypeError):
            amt = 0.0
        done[0] += 1
        if done[0] % 500 == 0:
            print('   ...%d/%d' % (done[0], len(meta)), file=sys.stderr)
        return (1 if pct > 0 else (-1 if pct < 0 else 0), is_lu, is_ld, amt)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(one, m) for m in meta]
        for fu in as_completed(futs):
            r = fu.result()
            if not r:
                continue
            d, a, b, amt = r
            if d > 0:
                up += 1
                amt_up += amt
            elif d < 0:
                down += 1
                amt_down += amt
                amt_notup += amt
            else:
                flat += 1
                amt_notup += amt
            if a:
                lu += 1
            if b:
                ld += 1
    return {'up': up, 'down': down, 'flat': flat, 'limit_up': lu, 'limit_down': ld,
            'total': up + down + flat, 'source': 'backfill',
            'amount_up_yi': fmt_amount(amt_up), 'amount_down_yi': fmt_amount(amt_down),
            'amount_notup_yi': fmt_amount(amt_notup),
            'up_notup_ratio': round(amt_up / amt_notup, 2) if amt_notup else None,
            'ratio_estimated': True}


# ---------------------------------------------------------------- 主流程

def stage_market(date_str):
    is_today = (date_str == today_str())
    print('[market] date=%s (%s)' % (date_str, '实时' if is_today else '历史'))
    idx, realtime = indices_for_date(date_str)
    if is_today and not is_trading_day(idx):
        print('[market] %s 非交易日（节假日），跳过' % date_str)
        return None
    patch = {'indices': list(idx.values()), 'realtime': realtime}

    if is_today:
        stocks = fetch_all_stocks()
        print('[market] 全市场个股 %d 只' % len(stocks))
        breadth = summarize_stocks(stocks)
        # 缓存名册，供后续回溯使用
        meta = [{'symbol': s['symbol'], 'code': s['code'], 'name': s['name']} for s in stocks]
        with open(os.path.join(CACHE_DIR, 'stock_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)
        patch['breadth'] = breadth
    else:
        old = load_day(date_str)
        if not (old and old.get('breadth')):
            patch['breadth'] = None   # 历史模式无法实时统计家数，已有回溯结果则保留

    dc = date_str.replace('-', '')
    try:
        js = fetch_limit_pool(dc)
        info = (js.get('data') or {}).get('info') or []
        total = ((js.get('data') or {}).get('page') or {}).get('total') or len(info)
        patch['limit_up_pool'] = {'total': total, 'ladder': parse_ladder(info)}
    except Exception as e:
        print('[warn] limit pool fail: %s' % e, file=sys.stderr)

    try:
        patch['hot_blocks'] = fetch_hot_blocks(dc)
    except Exception as e:
        print('[warn] hot blocks fail: %s' % e, file=sys.stderr)

    patch['funds'] = fetch_funds(date_str)
    patch['commodities'] = {
        'sp500': fetch_sp500(90),
        'brent': fetch_commodity('OIL', 90),
        'gold': fetch_commodity('GC', 90),
    }
    d = upsert_day(date_str, patch)
    print('[market] saved -> data/%s.json' % date_str)
    return d


def stage_lhb(date_str):
    print('[lhb] date=%s' % date_str)
    lhb = fetch_lhb(date_str)
    if not lhb['count']:
        print('[lhb] 当日无龙虎榜数据（非交易日或尚未公布），跳过写入')
        return None
    d = upsert_day(date_str, {'lhb': lhb,
                              'lhb_updated_at': now_bj()})
    print('[lhb] %d 条 -> data/%s.json' % (lhb['count'], date_str))
    return d


def stage_backfill(date_str):
    print('[backfill] date=%s' % date_str)
    b = backfill_breadth(date_str)
    d = upsert_day(date_str, {'breadth': b})
    print('[backfill] up=%d down=%d flat=%d lu=%d ld=%d' %
          (b['up'], b['down'], b['flat'], b['limit_up'], b['limit_down']))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=['market', 'lhb', 'backfill'], default='market')
    ap.add_argument('--date', default=None, help='YYYY-MM-DD，默认今天')
    args = ap.parse_args()
    date_str = args.date or today_str()

    if args.stage == 'market':
        stage_market(date_str)
    elif args.stage == 'lhb':
        stage_lhb(date_str)
    else:
        stage_backfill(date_str)


if __name__ == '__main__':
    main()
