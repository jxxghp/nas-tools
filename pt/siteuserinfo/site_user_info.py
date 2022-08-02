# -*- coding: utf-8 -*-
import json
import re
from abc import ABCMeta, abstractmethod
from urllib.parse import urljoin, urlsplit

import requests
from lxml import etree

from utils.http_utils import RequestUtils


class ISiteUserInfo(metaclass=ABCMeta):
    # 站点模版
    _site_schema = None

    def __init__(self, site_name, url, site_cookie, index_html, session=None):
        super().__init__()
        # 站点信息
        self.site_name = None
        self.site_url = None
        self.site_favicon = None
        # 用户信息
        self.username = None
        self.userid = None

        # 流量信息
        self.upload = 0
        self.download = 0
        self.ratio = 0

        # 种子信息
        self.seeding = 0
        self.leeching = 0
        self.uploaded = 0
        self.completed = 0
        self.incomplete = 0
        self.seeding_size = 0
        self.leeching_size = 0
        self.uploaded_size = 0
        self.completed_size = 0
        self.incomplete_size = 0
        # 做种人数, 种子大小
        self.seeding_info = []

        # 用户详细信息
        self.user_level = None
        self.join_at = None
        self.bonus = 0.0

        # 错误信息
        self.err_msg = None
        # 内部数据
        self._base_url = None
        self._site_cookie = None
        self._index_html = None

        # 站点页面
        self._brief_page = "index.php"
        self._user_detail_page = "userdetails.php?id="
        self._user_traffic_page = "index.php"
        self._torrent_seeding_page = "getusertorrentlistajax.php?userid="
        self._torrent_seeding_params = None

        split_url = urlsplit(url)
        self.site_name = site_name
        self.site_url = url
        self._base_url = f"{split_url.scheme}://{split_url.netloc}"
        self.site_favicon = urljoin(self._base_url, "favicon.ico")
        self._site_cookie = site_cookie
        self._index_html = index_html
        self._session = session if session else requests.Session()

    def site_schema(self):
        """
        站点解析模型
        :return:
        """
        return self._site_schema

    def parse(self):
        """
        解析站点信息
        :return:
        """
        self._parse_favicon(self._index_html)
        self._parse_site_page(self._index_html)
        self._parse_user_base_info(self._index_html)
        if self._user_traffic_page:
            self._parse_user_traffic_info(self._get_page_content(urljoin(self._base_url, self._user_traffic_page)))
        if self._user_detail_page:
            self._parse_user_detail_info(self._get_page_content(urljoin(self._base_url, self._user_detail_page)))

        seeding_pages = []
        if self._torrent_seeding_page:
            if isinstance(self._torrent_seeding_page, list):
                seeding_pages.extend(self._torrent_seeding_page)
            else:
                seeding_pages.append(self._torrent_seeding_page)

            for seeding_page in seeding_pages:
                # 第一页
                next_page = self._parse_user_torrent_seeding_info(
                    self._get_page_content(urljoin(self._base_url, seeding_page), self._torrent_seeding_params))

                # 其他页处理
                while next_page:
                    next_page = self._parse_user_torrent_seeding_info(
                        self._get_page_content(urljoin(urljoin(self._base_url, seeding_page), next_page),
                                               self._torrent_seeding_params),
                        multi_page=True)

        self.seeding_info = json.dumps(self.seeding_info)

    @staticmethod
    def _prepare_html_text(html_text):
        """
        处理掉HTML中的干扰部分
        """
        return re.sub(r"#\d+", "", re.sub(r"\d+px", "", html_text))

    def _parse_favicon(self, html_text):
        """
        解析站点favicon地址，head link中指定地址，使用指定，否则用默认
        :param html_text:
        :return:
        """
        html = etree.HTML(html_text)
        if not html:
            return

        fav_link = html.xpath('//head/link[@rel = "shortcut icon"]/@href')
        if fav_link:
            self.site_favicon = urljoin(self._base_url, fav_link[0])

    def _get_page_content(self, url, params=None):
        """
        :param url: 网页地址
        :param params: post参数
        :return:
        """
        if params:
            res = RequestUtils(cookies=self._site_cookie, session=self._session, timeout=60).post_res(url=url,
                                                                                                      params=params)
        else:
            res = RequestUtils(cookies=self._site_cookie, session=self._session, timeout=60).get_res(url=url)
        if res and res.status_code == 200:
            if "charset=utf-8" in res.text or "charset=UTF-8" in res.text:
                res.encoding = "UTF-8"
            else:
                res.encoding = res.apparent_encoding
            return res.text

        return ""

    @abstractmethod
    def _parse_site_page(self, html_text):
        """
        解析站点相关信息页面
        :param html_text:
        :return:
        """
        pass

    @abstractmethod
    def _parse_user_base_info(self, html_text):
        """
        解析用户基础信息
        :param html_text:
        :return:
        """
        pass

    @abstractmethod
    def _parse_user_traffic_info(self, html_text):
        """
        解析用户的上传，下载，分享率等信息
        :param html_text:
        :return:
        """
        pass

    @abstractmethod
    def _parse_user_torrent_seeding_info(self, html_text, multi_page=False):
        """
        解析用户的做种相关信息
        :param html_text:
        :param multi_page: 是否多页数据
        :return: 下页地址
        """
        pass

    @abstractmethod
    def _parse_user_detail_info(self, html_text):
        """
        解析用户的详细信息
        加入时间/等级/魔力值等
        :param html_text:
        :return:
        """
        pass
