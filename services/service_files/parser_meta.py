from enum import IntEnum
import operator
import re
from collections.abc import Container
import six
import click
from operator import attrgetter
from urllib.request import Request, urlopen
import json
import pandas as pd
from typing import Union

import urllib
import urllib.request
import html.parser
import requests
from requests.exceptions import HTTPError
from socket import error as SocketError
from http.cookiejar import CookieJar

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager

__all__ = ['FinamExportError', 'FinamDownloadError', 'FinamThrottlingError', 'FinamParsingError',
           'FinamObjectNotFoundError', 'FinamTooLongTimeframeError', 'FinamAlreadyInProgressError']

FINAM_CHARSET = 'cp1251'
#FINAM_TRUSTED_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) ' \
#                            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
FINAM_TRUSTED_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) ' \
                           'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'

FINAM_BASE = 'https://www.finam.ru'
FINAM_ENTRY_URL = FINAM_BASE + '/profile/moex-akcii/gazprom/export/'
FINAM_META_FILENAME = 'icharts.js'
FINAM_CATEGORIES = -1


class FinamExportError(Exception):
    pass


class FinamDownloadError(FinamExportError):
    pass


class FinamThrottlingError(FinamExportError):
    pass


class FinamParsingError(FinamExportError):
    pass


class FinamObjectNotFoundError(FinamExportError):
    pass


class FinamTooLongTimeframeError(FinamExportError):
    pass


class FinamAlreadyInProgressError(FinamExportError):
    pass


class FetchMetaWebriver:
    driver: Union[WebDriver, None] = None
    pages_to_load_max = 0
    pages_to_load_cur = {}
    timeout = 30
    wait: WebDriverWait

    def __enter__(self):
        cls = self.__class__
        if cls.driver and cls.pages_to_load_cur[id(cls.driver)] > 0:
            return self
        else:
            # chrome_service = Service(ChromeDriverManager().install())
            chrome_service = Service(executable_path='/usr/local/bin/chromedriver')
            chrome_options = Options()
            # Basic driver`s options
            chrome_options.add_argument('--disable-translate')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--headless')
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument(f'user-agent={FINAM_TRUSTED_USER_AGENT}')
            # Disable images and css loading
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.stylesheets": 2,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            # Setup driver and cache it inside the class
            cls.driver = webdriver.Chrome(service=chrome_service, options=chrome_options) # check change
            cls.wait = WebDriverWait(cls.driver, cls.timeout)
            cls.pages_to_load_cur[id(self.driver)] = cls.pages_to_load_max
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        cls = self.__class__
        cls.pages_to_load_cur[id(self.driver)] -= 1
        if any((exc_type, exc_val, exc_tb)):
            self.driver.quit()
        if cls.pages_to_load_cur[id(self.driver)] == 0:
            self.driver.quit()


def is_container(val):
    """

    :param val:
    :return:
    """
    is_c = isinstance(val, Container)
    return is_c and not isinstance(val, six.string_types) and not isinstance(val, bytes)


def smart_encode(val, charset=FINAM_CHARSET):
    """

    :param val:
    :param charset:
    :return:
    """
    if is_container(val):
        return [v.encode(charset) for v in val]
    return val.encode(charset)


def smart_decode(val, charset=FINAM_CHARSET):
    """

    :param val:
    :param charset:
    :return:
    """
    if is_container(val):
        return [v.decode(charset) for v in val]
    return val.decode(charset)


def build_trusted_request(url):
    """

    :param url:
    :return:
    """
    headers = {'User-Agent': FINAM_TRUSTED_USER_AGENT}
    return Request(url, None, headers)


def parse_script_link(html, src_entry):
    """

    :param html:
    :param src_entry:
    :return:
    """
#    print(src_entry)
    re_src_entry = re.escape(src_entry)
    pattern = '<script src="([^"]*{}[^"]*)"'.format(re_src_entry)
    match = re.search(pattern, html)
    if match is None:
        raise ValueError
    return match.group(1)


def click_validate_enum(enum_class, value):
    """

    :param enum_class:
    :param value:
    :return:
    """
    if value is not None:
        try:
            enum_class[value]
        except KeyError:
            allowed = map(attrgetter('name'), enum_class)
            raise click.BadParameter('allowed values: {}'
                                     .format(', '.join(allowed)))
    return value


class LookupComparator(IntEnum):
    EQUALS = 1
    STARTSWITH = 2
    CONTAINS = 3


def fetch_url(url, lines=False, sel=False):
    """

    :param url:
    :param lines:
    :param sel:
    :return:
    """

    if sel:
        locator = (By.XPATH, "//*")
        with FetchMetaWebriver() as fetcher:
            fetcher.driver.get(FINAM_ENTRY_URL)
            response = fetcher.wait.until(
                lambda driver: driver.find_element(*locator).get_attribute('outerHTML')
            )
#        print(f'RESPONSE SELENIUM - {response}')
        return response
    else:
        try:
            # url_data = 'https://www.finam.ru/' + 'cache/N72Hgd54/icharts/icharts.js'
            # req = urllib.request.Request(url_data, None, {
            #     'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
            #     'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            #     # 'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            #     # 'Accept-Encoding': 'gzip, deflate, sdch',
            #     # 'Accept-Language': 'ru-RU,en-US,en;q=0.8',
            #     # 'Connection': 'keep-alive'
            # })
            request = build_trusted_request(url)
            cj = CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            response = opener.open(request)
            if lines:
                raw_response = response.readlines()
            else:
                raw_response = response.read()
            raw_response = smart_decode(raw_response)
            response.close()
            return raw_response
        except urllib.request.HTTPError as inst:
            output = format(inst)
            print(output)
        # print(url)
        # request = build_trusted_request(url)
        # print(request)
        # try:
        #     fh = urlopen(request)
        #     if lines:
        #         response = fh.readlines()
        #     else:
        #         response = fh.read()
        #     # print(f'RESPONSE - {fh.msg}')
        #     # print(f'RESPONSE - {fh.status}')
        # except IOError as e:
        #     raise FinamDownloadError('Unable to load {}: {}'.format(url, e))
        #
        # try:
        #     return smart_decode(response)
        # except UnicodeDecodeError as e:
        #     raise FinamDownloadError('Unable to decode: {}'.format(e))


class ExporterMetaPage(object):
    """

    """
    def __init__(self, fetcher=fetch_url):
        self._fetcher = fetcher

    def find_meta_file(self):
        """

        :return:
        """
        html = self._fetcher(FINAM_ENTRY_URL, sel=True)
 #       print(f'RESPONSE - {html}')
        try:
            url = parse_script_link(html, FINAM_META_FILENAME)
            print(f'FIND URL - {url}')
        except ValueError as e:
            raise FinamParsingError('Unable to parse meta url from html: {}'.format(e))
        return FINAM_BASE + url


class ExporterMetaFile(object):
    """

    """
    def __init__(self, url, fetcher=fetch_url):
        self._url = url
        self._fetcher = fetcher

    @staticmethod
    def _parse_js_assignment(line):
        """

        :param line:
        :return:
        """
        start_char, end_char = '[', ']'
        start_idx = line.find(start_char)
        end_idx = line.find(end_char)
        if (start_idx == -1) or (end_idx == -1):
            raise FinamDownloadError('Unable to parse line: {}'.format(line))
        items = line[start_idx + 1:end_idx]

        if items.startswith("'"):
            items = items.split("','")
            for i in (0, -1):
                items[i] = items[i].strip("'")
            return items

        return items.split(',')

    def _parse_js(self, data):
        """

        :param data:
        :return:
        """
        print(data)
        cols = ['id', 'name', 'code', 'market']
        parsed = dict()
        urls = data[8][19:-1]
        urls = json.loads(urls)

        for idx, col in enumerate(cols[:len(cols)]):
            parsed[col] = self._parse_js_assignment(data[idx])
        cols.append('url')
        parsed['url'] = [urls[str(_id)].split('/')[-1] for _id in parsed['id']]

        df = pd.DataFrame(columns=cols, data=parsed)
        df['market'] = df['market'].astype(int)

        df = df[df.market != FINAM_CATEGORIES]

        df['id'] = df['id'].astype(int)
        df.set_index('id', inplace=True)
        df.sort_values('market', inplace=True)
        return df

    def parse_df(self):
        response = self._fetcher(self._url, lines=True)
        return self._parse_js(response)


class ExporterMeta(object):
    """

    """
    def __init__(self, lazy=True, fetcher=fetch_url):
        self._meta = None
        self._fetcher = fetcher
        if not lazy:
            self._load()

    def _load(self):
        """

        :return:
        """
        if self._meta is not None:
            return self._meta
        page = ExporterMetaPage(self._fetcher)
        meta_url = page.find_meta_file()
        meta_file = ExporterMetaFile(meta_url, self._fetcher)
        self._meta = meta_file.parse_df()

    @property
    def meta(self):
        """

        :return:
        """
        return self._meta.copy(deep=True)

    def _apply_filter(self, col, val, comparator):
        """

        :param col:
        :param val:
        :param comparator:
        :return:
        """
        if not is_container(val):
            val = [val]

        if comparator == LookupComparator.EQUALS:
            if col == 'id':
                expr = self._meta.index.isin(val)
            else:
                expr = self._meta[col].isin(val)
        else:
            if comparator == LookupComparator.STARTSWITH:
                op = 'startswith'
            else:
                op = 'contains'
            expr = self._combine_filters(
                map(getattr(self._meta[col].str, op), val), operator.or_)
        return expr

    @staticmethod
    def _combine_filters(filters, op):
        """

        :param filters:
        :param op:
        :return:
        """
        itr = iter(filters)
        result = next(itr)
        for filter_ in itr:
            result = op(result, filter_)
        return result

    def lookup(self, id_=None, code=None, name=None, market=None,
               name_comparator=LookupComparator.CONTAINS,
               code_comparator=LookupComparator.EQUALS):
        """

        :param id_:
        :param code:
        :param name:
        :param market:
        :param name_comparator:
        :param code_comparator:
        :return:
        """
        if not any((id_, code, name, market)):
            raise ValueError('Either id or code or name or market must be specified')

        self._load()
        filters = []

        filter_groups = (('id', id_, LookupComparator.EQUALS),
                         ('code', code, code_comparator),
                         ('name', name, name_comparator),
                         ('market', market, LookupComparator.EQUALS))

        for col, val, comparator in filter_groups:
            if val is not None:
                filters.append(self._apply_filter(col, val, comparator))

        combined_filter = self._combine_filters(filters, operator.and_)
        res = self._meta[combined_filter]
        if len(res) == 0:
            raise FinamObjectNotFoundError
        return res
