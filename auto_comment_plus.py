# -*- coding: utf-8 -*-
# @Time : 2022/2/8 20:50
# @Author : @qiu-lzsnmb and @Dimlitter
# @File : auto_comment_plus.py

import argparse
import copy
import logging
import os
import random
import sys
import time

import jieba  # just for linting
import jieba.analyse
import requests
import yaml
from lxml import etree

import jdspider

# constants
CONFIG_PATH = './config.yml'
USER_CONFIG_PATH = './config.user.yml'
ORDINARY_SLEEP_SEC = 10
SUNBW_SLEEP_SEC = 5
REVIEW_SLEEP_SEC = 10
SERVICE_RATING_SLEEP_SEC = 15

## logging with styles
## Reference: https://stackoverflow.com/a/384125/12002560
_COLORS = {
    'black': 0,
    'red': 1,
    'green': 2,
    'yellow': 3,
    'blue': 4,
    'magenta': 5,
    'cyan': 6,
    'white': 7
}

_RESET_SEQ = '\033[0m'
_COLOR_SEQ = '\033[1;%dm'
_BOLD_SEQ = '\033[1m'
_ITALIC_SEQ = '\033[3m'
_UNDERLINED_SEQ = '\033[4m'

_FORMATTER_COLORS = {
    'DEBUG': _COLORS['blue'],
    'INFO': _COLORS['green'],
    'WARNING': _COLORS['yellow'],
    'ERROR': _COLORS['red'],
    'CRITICAL': _COLORS['red']
}


def format_style_seqs(msg, use_style=True):
    if use_style:
        msg = msg.replace('$RESET', _RESET_SEQ)
        msg = msg.replace('$BOLD', _BOLD_SEQ)
        msg = msg.replace('$ITALIC', _ITALIC_SEQ)
        msg = msg.replace('$UNDERLINED', _UNDERLINED_SEQ)
    else:
        msg = msg.replace('$RESET', '')
        msg = msg.replace('$BOLD', '')
        msg = msg.replace('$ITALIC', '')
        msg = msg.replace('$UNDERLINED', '')


class StyleFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, use_style=True):
        logging.Formatter.__init__(self, fmt, datefmt)
        self.use_style = use_style

    def format(self, record):
        rcd = copy.copy(record)
        levelname = rcd.levelname
        if self.use_style and levelname in _FORMATTER_COLORS:
            levelname_with_color = '%s%s%s' % (
                _COLOR_SEQ % (30 + _FORMATTER_COLORS[levelname]),
                levelname, _RESET_SEQ)
            rcd.levelname = levelname_with_color
        return logging.Formatter.format(self, rcd)


# 评价生成
def generation(pname, _class=0, _type=1, opts=None):
    opts = opts or {}
    items = ['商品名']
    items.clear()
    items.append(pname)
    opts['logger'].debug('Items: %s', items)
    loop_times = len(items)
    opts['logger'].debug('Total loop times: %d', loop_times)
    for i, item in enumerate(items):
        opts['logger'].debug('Loop: %d / %d', i + 1, loop_times)
        opts['logger'].debug('Current item: %s', item)
        spider = jdspider.JDSpider(item)
        opts['logger'].debug('Successfully created a JDSpider instance')
        # 增加对增值服务的评价鉴别
        if "赠品" in pname or "非实物" in pname or "增值服务" in pname:
            result = [
                "赠品挺好的。",
                "很贴心，能有这样免费赠送的赠品!",
                "正好想着要不要多买一份增值服务，没想到还有这样的赠品。",
                "赠品正合我意。",
                "赠品很好，挺不错的。",
                "本来买了产品以后还有些担心。但是看到赠品以后就放心了。",
                "不论品质如何，至少说明店家对客的态度很好！",
                "我很喜欢这些商品！",
                "我对于商品的附加值很在乎，恰好这些赠品为这件商品提供了这样的的附加值，这令我很满意。"
                "感觉现在的网购环境环境越来越好了，以前网购的时候还没有过么多贴心的赠品和增值服务",
                "第一次用京东，被这种赠品和增值服物的良好态度感动到了。",
                "赠品还行。"
            ]
        else:
            result = spider.get_data(4, 3)  # 这里可以自己改
        opts['logger'].debug('Result: %s', result)

    # class 0是评价 1是提取id
    try:
        name = jieba.analyse.textrank(pname, topK=5, allowPOS='n')[0]
        opts['logger'].debug('Name: %s', name)
    except Exception as e:
        opts['logger'].warning(
            'jieba textrank analysis error: %s, name fallback to "宝贝"', e)
        name = "宝贝"
    if _class == 1:
        opts['logger'].debug('_class is 1. Directly return name')
        return name
    else:
        if _type == 1:
            num = 6
        elif _type == 0:
            num = 4
        num = min(num, len(result))
        # use `.join()` to improve efficiency
        comments = ''.join(random.sample(result, num))
        opts['logger'].debug('_type: %d', _type)
        opts['logger'].debug('num: %d', num)
        opts['logger'].debug('Raw comments: %s', comments)

        return 5, comments.replace("$", name)


# 查询全部评价
def all_evaluate(opts=None):
    opts = opts or {}
    N = {}
    url = 'https://club.jd.com/myJdcomments/myJdcomment.action?'
    opts['logger'].debug('URL: %s', url)
    opts['logger'].debug('Fetching website data')
    req = requests.get(url, headers=headers)
    opts['logger'].debug(
        'Successfully accepted the response with status code %d',
        req.status_code)
    if not req.ok:
        opts['logger'].warning(
            'Status code of the response is %d, not 200', req.status_code)
    req_et = etree.HTML(req.text)
    opts['logger'].debug('Successfully parsed an XML tree')
    evaluate_data = req_et.xpath('//*[@id="main"]/div[2]/div[1]/div/ul/li')
    # print(evaluate)
    loop_times = len(evaluate_data)
    opts['logger'].debug('Total loop times: %d', loop_times)
    for i, ev in enumerate(evaluate_data):
        opts['logger'].debug('Loop: %d / %d', i + 1, loop_times)
        na = ev.xpath('a/text()')[0]
        opts['logger'].debug('na: %s', na)
        try:
            num = ev.xpath('b/text()')[0]
            opts['logger'].debug('num: %s', num)
        except IndexError:
            opts['logger'].warning(
                'Can\'t find num content in XPath, fallback to 0')
            num = 0
        N[na] = int(num)
    return N


# 普通评价
def ordinary(N, opts=None):
    opts = opts or {}
    Order_data = []
    req_et = []
    loop_times = N['待评价订单'] // 20
    opts['logger'].debug('Fetching website data')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for i in range(loop_times + 1):
        url = (f'https://club.jd.com/myJdcomments/myJdcomment.action?sort=0&'
               f'page={i + 1}')
        opts['logger'].debug('URL: %s', url)
        req = requests.get(url, headers=headers)
        opts['logger'].debug(
            'Successfully accepted the response with status code %d',
            req.status_code)
        if not req.ok:
            opts['logger'].warning(
                'Status code of the response is %d, not 200', req.status_code)
        req_et.append(etree.HTML(req.text))
        opts['logger'].debug('Successfully parsed an XML tree')
    opts['logger'].debug('Fetching data from XML trees')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for idx, i in enumerate(req_et):
        opts['logger'].debug('Loop: %d / %d', idx + 1, loop_times)
        opts['logger'].debug('Fetching order data in the default XPath')
        elems = i.xpath(
            '//*[@id="main"]/div[2]/div[2]/table/tbody')
        opts['logger'].debug('Count of fetched order data: %d', len(elems))
        Order_data.extend(elems)
    if len(Order_data) != N['待评价订单']:
        opts['logger'].debug(
            'Count of fetched order data doesn\'t equal N["待评价订单"]')
        opts['logger'].debug('Clear the list Order_data')
        Order_data = []
        opts['logger'].debug('Total loop times: %d', loop_times)
        for idx, i in enumerate(req_et):
            opts['logger'].debug('Loop: %d / %d', idx + 1, loop_times)
            opts['logger'].debug('Fetching order data in another XPath')
            elems = i.xpath(
                '//*[@id="main"]/div[2]/div[2]/table')
            opts['logger'].debug('Count of fetched order data: %d', len(elems))
            Order_data.extend(elems)

    opts['logger'].info(f"当前共有{N['待评价订单']}个评价。")
    opts['logger'].debug('Commenting on items')
    for i, Order in enumerate(Order_data):
        try:
            oid = Order.xpath('tr[@class="tr-th"]/td/span[3]/a/text()')[0]
            opts['logger'].debug('oid: %s', oid)
            oname_data = Order.xpath(
                'tr[@class="tr-bd"]/td[1]/div[1]/div[2]/div/a/text()')
            opts['logger'].debug('oname_data: %s', oname_data)
            pid_data = Order.xpath(
                'tr[@class="tr-bd"]/td[1]/div[1]/div[2]/div/a/@href')
            opts['logger'].debug('pid_data: %s', pid_data)
        except IndexError:
            opts['logger'].warning(f"第{i + 1}个订单未查找到商品，跳过。")
            continue
        loop_times1 = min(len(oname_data), len(pid_data))
        opts['logger'].debug('Commenting on orders')
        opts['logger'].debug('Total loop times: %d', loop_times1)
        idx = 0
        for oname, pid in zip(oname_data, pid_data):
            opts['logger'].debug('Loop: %d / %d', idx + 1, loop_times1)
            pid = pid.replace('//item.jd.com/', '').replace('.html', '')
            opts['logger'].debug('pid: %s', pid)
            opts['logger'].info(f"\t{i}.开始评价订单\t{oname}[{oid}]")
            url2 = "https://club.jd.com/myJdcomments/saveProductComment.action"
            opts['logger'].debug('URL: %s', url2)
            xing, Str = generation(oname, opts=opts)
            opts['logger'].info(f'\t\t评价内容,星级{xing}：' + Str)
            data2 = {
                'orderId': oid,
                'productId': pid,  # 商品id
                'score': str(xing),  # 商品几星
                'content': bytes(Str, encoding="gbk"),  # 评价内容
                'saveStatus': '1',
                'anonymousFlag': '1'
            }
            opts['logger'].debug('Data: %s', data2)
            if not opts.get('dry_run'):
                opts['logger'].debug('Sending comment request')
                pj2 = requests.post(url2, headers=headers, data=data2)
            else:
                opts['logger'].debug(
                    'Skipped sending comment request in dry run')
            opts['logger'].debug('Sleep time (s): %.1f', ORDINARY_SLEEP_SEC)
            time.sleep(ORDINARY_SLEEP_SEC)
            idx += 1
    N['待评价订单'] -= 1
    return N


'''
# 晒单评价
def sunbw(N, opts=None):
    opts = opts or {}
    Order_data = []
    loop_times = N['待晒单'] // 20
    opts['logger'].debug('Fetching website data')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for i in range(loop_times + 1):
        opts['logger'].debug('Loop: %d / %d', i + 1, loop_times)
        url = (f'https://club.jd.com/myJdcomments/myJdcomment.action?sort=1'
               f'&page={i + 1}')
        opts['logger'].debug('URL: %s', url)
        req = requests.get(url, headers=headers)
        opts['logger'].debug(
            'Successfully accepted the response with status code %d',
            req.status_code)
        if not req.ok:
            opts['logger'].warning(
                'Status code of the response is %d, not 200', req.status_code)
        req_et = etree.HTML(req.text)
        opts['logger'].debug('Successfully parsed an XML tree')
        opts['logger'].debug('Fetching data from XML trees')
        elems = req_et.xpath(
            '//*[@id="evalu01"]/div[2]/div[1]/div[@class="comt-plist"]/div[1]')
        opts['logger'].debug('Count of fetched order data: %d', len(elems))
        Order_data.extend(elems)
    opts['logger'].info(f"当前共有{N['待晒单']}个需要晒单。")
    opts['logger'].debug('Commenting on items')
    for i, Order in enumerate(Order_data):
        oname = Order.xpath('ul/li[1]/div/div[2]/div[1]/a/text()')[0]
        pid = Order.xpath('@pid')[0]
        oid = Order.xpath('@oid')[0]
        opts['logger'].info(f'\t开始第{i + 1}，{oname}')
        opts['logger'].debug('pid: %s', pid)
        opts['logger'].debug('oid: %s', oid)
        # 获取图片
        url1 = (f'https://club.jd.com/discussion/getProductPageImageCommentList'
                f'.action?productId={pid}')
        opts['logger'].debug('Fetching images using the default URL')
        opts['logger'].debug('URL: %s', url1)
        req1 = requests.get(url1, headers=headers)
        opts['logger'].debug(
            'Successfully accepted the response with status code %d',
            req1.status_code)
        if not req.ok:
            opts['logger'].warning(
                'Status code of the response is %d, not 200', req1.status_code)
        imgdata = req1.json()
        opts['logger'].debug('Image data: %s', imgdata)
        if imgdata["imgComments"]["imgCommentCount"] == 0:
            opts['logger'].debug('Count of fetched image comments is 0')
            opts['logger'].debug('Fetching images using another URL')
            url1 = ('https://club.jd.com/discussion/getProductPageImage'
                    'CommentList.action?productId=1190881')
            opts['logger'].debug('URL: %s', url1)
            req1 = requests.get(url1, headers=headers)
            opts['logger'].debug(
                'Successfully accepted the response with status code %d',
                req1.status_code)
            if not req.ok:
                opts['logger'].warning(
                    'Status code of the response is %d, not 200',
                    req1.status_code)
            imgdata = req1.json()
            opts['logger'].debug('Image data: %s', imgdata)
        imgurl = imgdata["imgComments"]["imgList"][0]["imageUrl"]
        opts['logger'].debug('Image URL: %s', imgurl)

        opts['logger'].info(f'\t\t图片url={imgurl}')
        # 提交晒单
        opts['logger'].debug('Preparing for commenting')
        url2 = "https://club.jd.com/myJdcomments/saveShowOrder.action"
        opts['logger'].debug('URL: %s', url2)
        headers['Referer'] = ('https://club.jd.com/myJdcomments/myJdcomment.'
                              'action?sort=1')
        headers['Origin'] = 'https://club.jd.com'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        opts['logger'].debug('New header for this request: %s', headers)
        data = {
            'orderId': oid,
            'productId': pid,
            'imgs': imgurl,
            'saveStatus': 3
        }
        opts['logger'].debug('Data: %s', data)
        if not opts.get('dry_run'):
            opts['logger'].debug('Sending comment request')
            req_url2 = requests.post(url2, data=data, headers=headers)
        else:
            opts['logger'].debug('Skipped sending comment request in dry run')
        opts['logger'].info('完成')
        opts['logger'].debug('Sleep time (s): %.1f', SUNBW_SLEEP_SEC)
        time.sleep(SUNBW_SLEEP_SEC)
        N['待晒单'] -= 1
    return N
'''


# 追评
def review(N, opts=None):
    opts = opts or {}
    req_et = []
    Order_data = []
    loop_times = N['待追评'] // 20
    opts['logger'].debug('Fetching website data')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for i in range(loop_times + 1):
        opts['logger'].debug('Loop: %d / %d', i + 1, loop_times)
        url = (f"https://club.jd.com/myJdcomments/myJdcomment.action?sort=3"
               f"&page={i + 1}")
        opts['logger'].debug('URL: %s', url)
        req = requests.get(url, headers=headers)
        opts['logger'].debug(
            'Successfully accepted the response with status code %d',
            req.status_code)
        if not req.ok:
            opts['logger'].warning(
                'Status code of the response is %d, not 200', req.status_code)
        req_et.append(etree.HTML(req.text))
        opts['logger'].debug('Successfully parsed an XML tree')
    opts['logger'].debug('Fetching data from XML trees')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for idx, i in enumerate(req_et):
        opts['logger'].debug('Loop: %d / %d', idx + 1, loop_times)
        opts['logger'].debug('Fetching order data in the default XPath')
        elems = i.xpath(
            '//*[@id="main"]/div[2]/div[2]/table/tr[@class="tr-bd"]')
        opts['logger'].debug('Count of fetched order data: %d', len(elems))
        Order_data.extend(elems)
    if len(Order_data) != N['待追评']:
        opts['logger'].debug(
            'Count of fetched order data doesn\'t equal N["待追评"]')
        # NOTE: Need them?
        # opts['logger'].debug('Clear the list Order_data')
        # Order_data = []
        opts['logger'].debug('Total loop times: %d', loop_times)
        for idx, i in enumerate(req_et):
            opts['logger'].debug('Loop: %d / %d', idx + 1, loop_times)
            opts['logger'].debug('Fetching order data in another XPath')
            elems = i.xpath(
                '//*[@id="main"]/div[2]/div[2]/table/tbody/tr[@class="tr-bd"]')
            opts['logger'].debug('Count of fetched order data: %d', len(elems))
            Order_data.extend(elems)
    opts['logger'].info(f"当前共有{N['待追评']}个需要追评。")
    opts['logger'].debug('Commenting on items')
    for i, Order in enumerate(Order_data):
        oname = Order.xpath('td[1]/div/div[2]/div/a/text()')[0]
        _id = Order.xpath('td[3]/div/a/@href')[0]
        opts['logger'].info(f'\t开始第{i + 1}，{oname}')
        opts['logger'].debug('_id: %s', _id)
        url1 = ("https://club.jd.com/afterComments/"
                "saveAfterCommentAndShowOrder.action")
        opts['logger'].debug('URL: %s', url1)
        pid, oid = _id.replace(
            'http://club.jd.com/afterComments/productPublish.action?sku=',
            "").split('&orderId=')
        opts['logger'].debug('pid: %s', pid)
        opts['logger'].debug('oid: %s', oid)
        _, context = generation(oname, _type=0, opts=opts)
        opts['logger'].info(f'\t\t追评内容：{context}')
        data1 = {
            'orderId': oid,
            'productId': pid,
            'content': bytes(context, encoding="gbk"),
            'anonymousFlag': 1,
            'score': 5
        }
        opts['logger'].debug('Data: %s', data1)
        if not opts.get('dry_run'):
            opts['logger'].debug('Sending comment request')
            req_url1 = requests.post(url1, headers=headers, data=data1)
        else:
            opts['logger'].debug('Skipped sending comment request in dry run')
        opts['logger'].info('完成')
        opts['logger'].debug('Sleep time (s): %.1f', REVIEW_SLEEP_SEC)
        time.sleep(REVIEW_SLEEP_SEC)
        N['待追评'] -= 1
    return N


# 服务评价
def Service_rating(N, opts=None):
    opts = opts or {}
    Order_data = []
    req_et = []
    loop_times = N['服务评价'] // 20
    opts['logger'].debug('Fetching website data')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for i in range(loop_times + 1):
        opts['logger'].debug('Loop: %d / %d', i + 1, loop_times)
        url = (f"https://club.jd.com/myJdcomments/myJdcomment.action?sort=4"
               f"&page={i + 1}")
        opts['logger'].debug('URL: %s', url)
        req = requests.get(url, headers=headers)
        opts['logger'].debug(
            'Successfully accepted the response with status code %d',
            req.status_code)
        if not req.ok:
            opts['logger'].warning(
                'Status code of the response is %d, not 200', req.status_code)
        req_et.append(etree.HTML(req.text))
        opts['logger'].debug('Successfully parsed an XML tree')
    opts['logger'].debug('Fetching data from XML trees')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for idx, i in enumerate(req_et):
        opts['logger'].debug('Loop: %d / %d', idx + 1, loop_times)
        opts['logger'].debug('Fetching order data in the default XPath')
        elems = i.xpath(
            '//*[@id="main"]/div[2]/div[2]/table/tbody/tr[@class="tr-bd"]')
        opts['logger'].debug('Count of fetched order data: %d', len(elems))
        Order_data.extend(elems)
    if len(Order_data) != N['服务评价']:
        opts['logger'].debug(
            'Count of fetched order data doesn\'t equal N["服务评价"]')
        opts['logger'].debug('Clear the list Order_data')
        Order_data = []
        opts['logger'].debug('Total loop times: %d', loop_times)
        for idx, i in enumerate(req_et):
            opts['logger'].debug('Loop: %d / %d', idx + 1, loop_times)
            opts['logger'].debug('Fetching order data in another XPath')
            elems = i.xpath(
                '//*[@id="main"]/div[2]/div[2]/table/tr[@class="tr-bd"]')
            opts['logger'].debug('Count of fetched order data: %d', len(elems))
            Order_data.extend(elems)
    opts['logger'].info(f"当前共有{N['服务评价']}个需要服务评价。")
    opts['logger'].debug('Commenting on items')
    for i, Order in enumerate(Order_data):
        oname = Order.xpath('td[1]/div[1]/div[2]/div/a/text()')[0]
        oid = Order.xpath('td[4]/div/a[1]/@oid')[0]
        opts['logger'].info(f'\t开始第{i + 1}，{oname}')
        opts['logger'].debug('oid: %s', oid)
        url1 = (f'https://club.jd.com/myJdcomments/insertRestSurvey.action'
                f'?voteid=145&ruleid={oid}')
        opts['logger'].debug('URL: %s', url1)
        data1 = {
            'oid': oid,
            'gid': '32',
            'sid': '186194',
            'stid': '0',
            'tags': '',
            'ro591': f'591A{random.randint(4, 5)}',  # 商品符合度
            'ro592': f'592A{random.randint(4, 5)}',  # 店家服务态度
            'ro593': f'593A{random.randint(4, 5)}',  # 快递配送速度
            'ro899': f'899A{random.randint(4, 5)}',  # 快递员服务
            'ro900': f'900A{random.randint(4, 5)}'  # 快递员服务
        }
        opts['logger'].debug('Data: %s', data1)
        if not opts.get('dry_run'):
            opts['logger'].debug('Sending comment request')
            pj1 = requests.post(url1, headers=headers, data=data1)
        else:
            opts['logger'].debug('Skipped sending comment request in dry run')
        opts['logger'].info("\t\t " + pj1.text)
        opts['logger'].debug('Sleep time (s): %.1f', SERVICE_RATING_SLEEP_SEC)
        time.sleep(SERVICE_RATING_SLEEP_SEC)
        N['服务评价'] -= 1
    return N


def No(opts=None):
    opts = opts or {}
    opts['logger'].info('')
    N = all_evaluate(opts)
    s = '----'.join(['{} {}'.format(i, N[i]) for i in N])
    opts['logger'].info(s)
    opts['logger'].info('')
    return N


def main(opts=None):
    opts = opts or {}
    opts['logger'].info("开始京东批量评价！")
    N = No(opts)
    opts['logger'].debug('N value after executing No(): %s', N)
    if not N:
        opts['logger'].error('Ck出现错误，请重新抓取！')
        exit()
    opts['logger'].info(f"已评价：{N['已评价']}个")
    if N['待评价订单'] != 0:
        opts['logger'].info("1.开始普通评价")
        N = ordinary(N, opts)
        opts['logger'].debug('N value after executing ordinary(): %s', N)
        N = No(opts)
        opts['logger'].debug('N value after executing No(): %s', N)
    ''' "待晒单" is no longer found in N{} instead of "已评价"
    if N['待晒单'] != 0:
        opts['logger'].info("2.开始晒单评价")
        N = sunbw(N, opts)
        opts['logger'].debug('N value after executing sunbw(): %s', N)
        N = No(opts)
        opts['logger'].debug('N value after executing No(): %s', N)
    '''
    if N['待追评'] != 0:
        opts['logger'].info("3.开始批量追评！")
        N = review(N, opts)
        opts['logger'].debug('N value after executing review(): %s', N)
        N = No(opts)
        opts['logger'].debug('N value after executing No(): %s', N)
    if N['服务评价'] != 0:
        opts['logger'].info('4.开始服务评价')
        N = Service_rating(N, opts)
        opts['logger'].debug('N value after executing Service_rating(): %s', N)
        N = No(opts)
        opts['logger'].debug('N value after executing No(): %s', N)
    opts['logger'].info("全部完成啦！")
    for i in N:
        if N[i] != 0:
            opts['logger'].warning("出现了二次错误，跳过了部分，重新尝试")
            main(opts)


if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run',
                        help='have a full run without comment submission',
                        action='store_true')
    parser.add_argument('--log-level',
                        help='specify logging level (default: info)',
                        default='INFO')
    parser.add_argument('-o', '--log-file', help='specify logging file')
    args = parser.parse_args()
    if args.log_level.upper() not in [
        'DEBUG', 'WARN', 'INFO', 'ERROR', 'FATAL'
        # NOTE: `WARN` is an alias of `WARNING`. `FATAL` is an alias of
        # `CRITICAL`. Using these aliases is for developers' and users'
        # convenience.
        # NOTE: Now there is no logging on `CRITICAL` level.
    ]:
        args.log_level = 'INFO'
    else:
        args.log_level = args.log_level.upper()
    opts = {
        'dry_run': args.dry_run,
        'log_level': args.log_level
    }
    if hasattr(args, 'log_file'):
        opts['log_file'] = args.log_file
    else:
        opts['log_file'] = None

    # logging on console
    _logging_level = getattr(logging, opts['log_level'])
    logger = logging.getLogger('comment')
    logger.setLevel(level=_logging_level)
    # NOTE: `%(levelname)s` will be parsed as the original name (`FATAL` ->
    # `CRITICAL`, `WARN` -> `WARNING`).
    # NOTE: The alignment number should set to 19 considering the style
    # controling characters. When it comes to file logger, the number should
    # set to 8.
    formatter = StyleFormatter('%(asctime)s %(levelname)-19s %(message)s')
    rawformatter = StyleFormatter('%(asctime)s %(levelname)-8s %(message)s', use_style=False)
    console = logging.StreamHandler()
    console.setLevel(_logging_level)
    console.setFormatter(formatter)
    logger.addHandler(console)
    opts['logger'] = logger
    # It's a hack!!!
    jieba.default_logger = logging.getLogger('jieba')
    jieba.default_logger.setLevel(level=_logging_level)
    jieba.default_logger.addHandler(console)
    # It's another hack!!!
    jdspider.default_logger = logging.getLogger('spider')
    jdspider.default_logger.setLevel(level=_logging_level)
    jdspider.default_logger.addHandler(console)

    logger.debug('Successfully set up console logger')
    logger.debug('CLI arguments: %s', args)
    logger.debug('Opening the log file')
    if opts['log_file']:
        try:
            handler = logging.FileHandler(opts['log_file'])
        except Exception as e:
            logger.error('Failed to open the file handler')
            logger.error('Error message: %s', e)
            sys.exit(1)
        handler.setLevel(_logging_level)
        handler.setFormatter(rawformatter)
        logger.addHandler(handler)
        jieba.default_logger.addHandler(handler)
        jdspider.default_logger.addHandler(handler)
        logger.debug('Successfully set up file logger')
    logger.debug('Options passed to functions: %s', opts)
    logger.debug('Builtin constants:')
    logger.debug('  CONFIG_PATH: %s', CONFIG_PATH)
    logger.debug('  USER_CONFIG_PATH: %s', USER_CONFIG_PATH)
    logger.debug('  ORDINARY_SLEEP_SEC: %s', ORDINARY_SLEEP_SEC)
    logger.debug('  SUNBW_SLEEP_SEC: %s', SUNBW_SLEEP_SEC)
    logger.debug('  REVIEW_SLEEP_SEC: %s', REVIEW_SLEEP_SEC)
    logger.debug('  SERVICE_RATING_SLEEP_SEC: %s', SERVICE_RATING_SLEEP_SEC)

    # parse configurations
    logger.debug('Reading the configuration file')
    if os.path.exists(USER_CONFIG_PATH):
        logger.debug('User configuration file exists')
        _cfg_path = USER_CONFIG_PATH
    else:
        logger.debug('User configuration file doesn\'t exist, fallback to the default one')
        _cfg_path = CONFIG_PATH
    with open(_cfg_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    logger.debug('Closed the configuration file')
    logger.debug('Configurations in Python-dict format: %s', cfg)
    cks = cfg['user']['cookies']
    logger.info(f"开始执行 {len(cks)} 个账号")
    for ck in cks:
        headers = {
            'cookie': ck.encode("utf-8"),
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Sec-Fetch-Site': 'same-site',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Referer': 'https://order.jd.com/',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        logger.debug('Builtin HTTP request header: %s', headers)

        logger.debug('Starting main processes')
        try:
            main(opts)
        # NOTE: It needs 3,000 times to raise this exception. Do you really want to
        # do like this?
        except RecursionError:
            logger.error("多次出现未完成情况，程序自动退出")
