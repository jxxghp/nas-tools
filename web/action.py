import importlib
import signal
from urllib import parse

from flask_login import logout_user
from werkzeug.security import generate_password_hash

import log
from config import RMT_MEDIAEXT, Config
from message.channel.telegram import Telegram
from message.channel.wechat import WeChat
from message.send import Message
from pt.brushtask import BrushTask
from pt.client.qbittorrent import Qbittorrent
from pt.client.transmission import Transmission
from pt.douban import DouBan
from pt.downloader import Downloader
from pt.filterrules import FilterRule
from pt.mediaserver.jellyfin import Jellyfin
from pt.mediaserver.plex import Plex
from pt.rss import Rss
from pt.siteconf import RSS_SITE_GRAP_CONF
from pt.sites import Sites
from pt.subtitle import Subtitle
from pt.torrent import Torrent
from rmt.category import Category
from rmt.doubanv2api.doubanapi import DoubanApi
from rmt.filetransfer import FileTransfer
from rmt.media import Media
from rmt.metainfo import MetaInfo
from service.run import stop_scheduler, stop_monitor, restart_scheduler, restart_monitor
from service.scheduler import Scheduler
from service.sync import Sync
from utils.commons import EpisodeFormat, ProcessHandler
from utils.functions import *
from utils.http_utils import RequestUtils
from utils.meta_helper import MetaHelper
from utils.sqls import *
from utils.sysmsg_helper import MessageCenter
from utils.thread_helper import ThreadHelper
from utils.types import MediaType, SearchType, DownloaderType, SyncType
from web.backend.douban_hot import DoubanHot
from web.backend.search_torrents import search_medias_for_web, search_media_by_message
from web.backend.subscribe import add_rss_subscribe


class WebAction:
    config = None
    _actions = {}

    def __init__(self):
        self.config = Config()
        self._actions = {
            "sch": self.__sch,
            "search": self.__search,
            "download": self.__download,
            "pt_start": self.__pt_start,
            "pt_stop": self.__pt_stop,
            "pt_remove": self.__pt_remove,
            "pt_info": self.__pt_info,
            "del_unknown_path": self.__del_unknown_path,
            "rename": self.__rename,
            "rename_udf": self.__rename_udf,
            "delete_history": self.__delete_history,
            "logging": self.__logging,
            "version": self.__version,
            "update_site": self.__update_site,
            "get_site": self.__get_site,
            "del_site": self.__del_site,
            "restart": self.__restart,
            "update_system": self.__update_system,
            "logout": self.__logout,
            "update_config": self.__update_config,
            "update_directory": self.__update_directory,
            "remove_rss_media": self.__remove_rss_media,
            "add_rss_media": self.__add_rss_media,
            "re_identification": self.__re_identification,
            "media_info": self.__media_info,
            "test_connection": self.__test_connection,
            "user_manager": self.__user_manager,
            "refresh_rss": self.__refresh_rss,
            "refresh_message": self.__refresh_message,
            "delete_tmdb_cache": self.__delete_tmdb_cache,
            "movie_calendar_data": self.__movie_calendar_data,
            "tv_calendar_data": self.__tv_calendar_data,
            "modify_tmdb_cache": self.__modify_tmdb_cache,
            "rss_detail": self.__rss_detail,
            "truncate_blacklist": self.__truncate_blacklist,
            "add_brushtask": self.__add_brushtask,
            "del_brushtask": self.__del_brushtask,
            "brushtask_detail": self.__brushtask_detail,
            "add_downloader": self.__add_downloader,
            "delete_downloader": self.__delete_downloader,
            "name_test": self.__name_test,
            "rule_test": self.__rule_test,
            "add_filtergroup": self.__add_filtergroup,
            "set_default_filtergroup": self.__set_default_filtergroup,
            "del_filtergroup": self.__del_filtergroup,
            "add_filterrule": self.__add_filterrule,
            "del_filterrule": self.__del_filterrule,
            "filterrule_detail": self.__filterrule_detail,
            "get_site_activity": self.__get_site_activity,
            "get_site_history": self.__get_site_history,
            "get_recommend": self.get_recommend,
            "get_downloaded": self.get_downloaded,
            "get_site_seeding_info": self.__get_site_seeding_info,
            "clear_tmdb_cache": self.__clear_tmdb_cache,
            "check_site_attr": self.__check_site_attr,
            "refresh_process": self.__refresh_process
        }

    def action(self, cmd, data):
        func = self._actions.get(cmd)
        if not func:
            return "??????????????????"
        else:
            return func(data)

    @staticmethod
    def stop_service():
        """
        ??????????????????
        """
        # ??????????????????
        stop_scheduler()
        # ????????????
        stop_monitor()
        # ??????
        logout_user()

    @staticmethod
    def shutdown_server():
        """
        ??????Flask??????
        """
        sig = getattr(signal, "SIGKILL", signal.SIGTERM)
        os.kill(os.getpid(), sig)

    @staticmethod
    def handle_message_job(msg, in_from=SearchType.OT, user_id=None):
        """
        ??????????????????
        """
        if not msg:
            return
        commands = {
            "/ptr": {"func": Downloader().pt_removetorrents, "desp": "PT??????"},
            "/ptt": {"func": Downloader().pt_transfer, "desp": "PT????????????"},
            "/pts": {"func": Sites().signin, "desp": "PT?????????"},
            "/rst": {"func": Sync().transfer_all_sync, "desp": "????????????????????????"},
            "/rss": {"func": Rss().rssdownload, "desp": "RSS??????"},
            "/db": {"func": DouBan().sync, "desp": "????????????"}
        }
        command = commands.get(msg)
        if command:
            # ??????????????????
            if in_from == SearchType.TG and user_id:
                if str(user_id) != Telegram().get_admin_user():
                    Message().send_channel_msg(channel=in_from, title="???????????????????????????????????????????????????")
                    return
            # ????????????
            ThreadHelper().start_thread(command.get("func"), ())
            Message().send_channel_msg(channel=in_from, title="%s ?????????" % command.get("desp"))
        else:
            # PT????????????????????????
            ThreadHelper().start_thread(search_media_by_message, (msg, in_from, user_id,))

    @staticmethod
    def set_config_value(cfg, cfg_key, cfg_value):
        """
        ??????Key???????????????
        """
        # ??????
        if cfg_key == "app.login_password":
            if cfg_value and not cfg_value.startswith("[hash]"):
                cfg['app']['login_password'] = "[hash]%s" % generate_password_hash(cfg_value)
            else:
                cfg['app']['login_password'] = cfg_value or "password"
            return cfg
        # ??????
        if cfg_key == "app.proxies":
            if cfg_value:
                if not cfg_value.startswith("http") and not cfg_value.startswith("sock"):
                    cfg['app']['proxies'] = {"https": "http://%s" % cfg_value, "http": "http://%s" % cfg_value}
                else:
                    cfg['app']['proxies'] = {"https": "%s" % cfg_value, "http": "%s" % cfg_value}
            else:
                cfg['app']['proxies'] = {"https": None, "http": None}
            return cfg
        # ??????????????????
        if cfg_key == "app.rmt_mode":
            cfg['sync']['sync_mod'] = cfg_value
            cfg['pt']['rmt_mode'] = cfg_value
            return cfg
        # ??????????????????
        if cfg_key == "douban.users":
            vals = cfg_value.split(",")
            cfg['douban']['users'] = vals
            return cfg
        # ?????????
        if cfg_key == "jackett.indexers":
            vals = cfg_value.split("\n")
            cfg['jackett']['indexers'] = vals
            return cfg
        # ????????????????????????
        keys = cfg_key.split(".")
        if keys:
            if len(keys) == 1:
                cfg[keys[0]] = cfg_value
            elif len(keys) == 2:
                if not cfg.get(keys[0]):
                    cfg[keys[0]] = {}
                cfg[keys[0]][keys[1]] = cfg_value
            elif len(keys) == 3:
                if cfg.get(keys[0]):
                    if not cfg[keys[0]].get(keys[1]) or isinstance(cfg[keys[0]][keys[1]], str):
                        cfg[keys[0]][keys[1]] = {}
                    cfg[keys[0]][keys[1]][keys[2]] = cfg_value
                else:
                    cfg[keys[0]] = {}
                    cfg[keys[0]][keys[1]] = {}
                    cfg[keys[0]][keys[1]][keys[2]] = cfg_value

        return cfg

    @staticmethod
    def set_config_directory(cfg, oper, cfg_key, cfg_value, update_value=None):
        """
        ??????????????????
        """
        # ????????????????????????
        keys = cfg_key.split(".")
        if keys:
            if len(keys) == 1:
                if cfg.get(keys[0]):
                    if not isinstance(cfg[keys[0]], list):
                        cfg[keys[0]] = [cfg[keys[0]]]
                    if oper == "add":
                        cfg[keys[0]].append(cfg_value)
                    elif oper == "sub":
                        cfg[keys[0]].remove(cfg_value)
                        if not cfg[keys[0]]:
                            cfg[keys[0]] = None
                    elif oper == "set":
                        cfg[keys[0]].remove(cfg_value)
                        if update_value:
                            cfg[keys[0]].append(update_value)
                else:
                    cfg[keys[0]] = cfg_value
            elif len(keys) == 2:
                if cfg.get(keys[0]):
                    if not cfg[keys[0]].get(keys[1]):
                        cfg[keys[0]][keys[1]] = []
                    if not isinstance(cfg[keys[0]][keys[1]], list):
                        cfg[keys[0]][keys[1]] = [cfg[keys[0]][keys[1]]]
                    if oper == "add":
                        cfg[keys[0]][keys[1]].append(cfg_value)
                    elif oper == "sub":
                        cfg[keys[0]][keys[1]].remove(cfg_value)
                        if not cfg[keys[0]][keys[1]]:
                            cfg[keys[0]][keys[1]] = None
                    elif oper == "set":
                        cfg[keys[0]][keys[1]].remove(cfg_value)
                        if update_value:
                            cfg[keys[0]][keys[1]].append(update_value)
                else:
                    cfg[keys[0]] = {}
                    cfg[keys[0]][keys[1]] = cfg_value
        return cfg

    @staticmethod
    def __sch(data):
        """
        ??????????????????
        """
        commands = {
            "autoremovetorrents": Downloader().pt_removetorrents,
            "pttransfer": Downloader().pt_transfer,
            "ptsignin": Sites().signin,
            "sync": Sync().transfer_all_sync,
            "rssdownload": Rss().rssdownload,
            "douban": DouBan().sync
        }
        sch_item = data.get("item")
        if sch_item and commands.get(sch_item):
            ThreadHelper().start_thread(commands.get(sch_item), ())
        return {"retmsg": "???????????????", "item": sch_item}

    @staticmethod
    def __search(data):
        """
        WEB????????????
        """
        search_word = data.get("search_word")
        ident_flag = False if data.get("unident") else True
        filters = data.get("filters")
        tmdbid = data.get("tmdbid")
        media_type = data.get("media_type")
        if media_type:
            if media_type == "??????":
                media_type = MediaType.MOVIE
            else:
                media_type = MediaType.TV
        if search_word:
            ret, ret_msg = search_medias_for_web(content=search_word,
                                                 ident_flag=ident_flag,
                                                 filters=filters,
                                                 tmdbid=tmdbid,
                                                 media_type=media_type)
            if ret != 0:
                return {"code": ret, "msg": ret_msg}
        return {"code": 0}

    @staticmethod
    def __download(data):
        """
        ???WEB????????????
        """
        dl_id = data.get("id")
        results = get_search_result_by_id(dl_id)
        for res in results:
            if res[11] and str(res[11]) != "0":
                msg_item = MetaInfo("%s" % res[8])
                if res[7] == "TV":
                    mtype = MediaType.TV
                elif res[7] == "MOV":
                    mtype = MediaType.MOVIE
                else:
                    mtype = MediaType.ANIME
                msg_item.type = mtype
                msg_item.tmdb_id = res[11]
                msg_item.title = res[1]
                msg_item.vote_average = res[5]
                msg_item.poster_path = res[6]
                msg_item.poster_path = res[12]
                msg_item.overview = res[13]
            else:
                msg_item = Media().get_media_info(title=res[8], subtitle=res[9])
            msg_item.enclosure = res[0]
            msg_item.description = res[9]
            msg_item.size = res[10]
            msg_item.site = res[14]
            msg_item.upload_volume_factor = float(res[15] or 1.0)
            msg_item.download_volume_factor = float(res[16] or 1.0)
            # ????????????
            ret, ret_msg = Downloader().add_pt_torrent(res[0], msg_item.type)
            if ret:
                # ????????????
                Message().send_download_message(SearchType.WEB, msg_item)
            else:
                return {"retcode": -1, "retmsg": ret_msg}
        return {"retcode": 0, "retmsg": ""}

    @staticmethod
    def __pt_start(data):
        """
        ????????????
        """
        tid = data.get("id")
        if id:
            Downloader().start_torrents(tid)
        return {"retcode": 0, "id": tid}

    @staticmethod
    def __pt_stop(data):
        """
        ????????????
        """
        tid = data.get("id")
        if id:
            Downloader().stop_torrents(tid)
        return {"retcode": 0, "id": tid}

    @staticmethod
    def __pt_remove(data):
        """
        ????????????
        """
        tid = data.get("id")
        if id:
            Downloader().delete_torrents(tid)
        return {"retcode": 0, "id": tid}

    @staticmethod
    def __pt_info(data):
        """
        ???????????????????????????
        """
        ids = data.get("ids")
        Client, Torrents = Downloader().get_torrents(torrent_ids=ids)
        DispTorrents = []
        for torrent in Torrents:
            if Client == DownloaderType.QB:
                if torrent.get('state') in ['pausedDL']:
                    state = "Stoped"
                    speed = "?????????"
                else:
                    state = "Downloading"
                    dlspeed = str_filesize(torrent.get('dlspeed'))
                    eta = str_timelong(torrent.get('eta'))
                    upspeed = str_filesize(torrent.get('upspeed'))
                    speed = "%s%sB/s %s%sB/s %s" % (chr(8595), dlspeed, chr(8593), upspeed, eta)
                # ??????
                progress = round(torrent.get('progress') * 100)
                # ??????
                key = torrent.get('hash')
            else:
                if torrent.status in ['stopped']:
                    state = "Stoped"
                    speed = "?????????"
                else:
                    state = "Downloading"
                    dlspeed = str_filesize(torrent.rateDownload)
                    upspeed = str_filesize(torrent.rateUpload)
                    speed = "%s%sB/s %s%sB/s" % (chr(8595), dlspeed, chr(8593), upspeed)
                # ??????
                progress = round(torrent.progress, 1)
                # ??????
                key = torrent.id

            torrent_info = {'id': key, 'speed': speed, 'state': state, 'progress': progress}
            if torrent_info not in DispTorrents:
                DispTorrents.append(torrent_info)
        return {"retcode": 0, "torrents": DispTorrents}

    @staticmethod
    def __del_unknown_path(data):
        """
        ????????????
        """
        tids = data.get("id")
        if isinstance(tids, list):
            for tid in tids:
                if not tid:
                    continue
                delete_transfer_unknown(tid)
            return {"retcode": 0}
        else:
            retcode = delete_transfer_unknown(tids)
            return {"retcode": retcode}

    @staticmethod
    def __rename(data):
        """
        ????????????
        """
        path = dest_dir = None
        logid = data.get("logid")
        if logid:
            paths = get_transfer_path_by_id(logid)
            if paths:
                path = os.path.join(paths[0][0], paths[0][1])
                dest_dir = paths[0][2]
            else:
                return {"retcode": -1, "retmsg": "??????????????????????????????"}
        else:
            unknown_id = data.get("unknown_id")
            if unknown_id:
                paths = get_unknown_path_by_id(unknown_id)
                if paths:
                    path = paths[0][0]
                    dest_dir = paths[0][1]
                else:
                    return {"retcode": -1, "retmsg": "???????????????????????????"}
        if not dest_dir:
            dest_dir = ""
        if not path:
            return {"retcode": -1, "retmsg": "??????????????????"}
        tmdbid = data.get("tmdb")
        title = data.get("title")
        year = data.get("year")
        mtype = data.get("type")
        season = data.get("season")
        episode_format = data.get("episode_format")
        min_filesize = data.get("min_filesize")
        if mtype == "TV":
            media_type = MediaType.TV
        elif mtype == "MOV":
            media_type = MediaType.MOVIE
        else:
            media_type = MediaType.ANIME
        tmdb_info = Media().get_tmdb_info(media_type, title, year, tmdbid)
        if not tmdb_info:
            return {"retcode": 1, "retmsg": "??????????????????????????????TMDB??????"}
        # ????????????????????????????????????????????????????????????????????????????????????????????????episode_format??????
        need_fix_all = False
        if os.path.splitext(path)[-1].lower() in RMT_MEDIAEXT and episode_format:
            path = os.path.dirname(path)
            need_fix_all = True
        succ_flag, ret_msg = FileTransfer().transfer_media(in_from=SyncType.MAN,
                                                           in_path=path,
                                                           target_dir=dest_dir,
                                                           tmdb_info=tmdb_info,
                                                           media_type=media_type,
                                                           season=season,
                                                           episode=(EpisodeFormat(episode_format), need_fix_all),
                                                           min_filesize=min_filesize
                                                           )
        if succ_flag:
            if not need_fix_all and not logid:
                update_transfer_unknown_state(path)
            return {"retcode": 0, "retmsg": "????????????"}
        else:
            return {"retcode": 2, "retmsg": ret_msg}

    @staticmethod
    def __rename_udf(data):
        """
        ???????????????
        """
        inpath = data.get("inpath")
        outpath = data.get("outpath")
        if not os.path.exists(inpath):
            return {"retcode": -1, "retmsg": "?????????????????????"}
        tmdbid = data.get("tmdb")
        if not tmdbid.strip() and not tmdbid.isdigit():
            return {"retcode": -1, "retmsg": "tmdbid ??????????????????"}
        mtype = data.get("type")
        season = data.get("season")
        episode_format = data.get("episode_format")
        episode_details = data.get("episode_details")
        episode_offset = data.get("episode_offset")
        min_filesize = data.get("min_filesize")
        if mtype == "TV":
            media_type = MediaType.TV
        elif mtype == "MOV":
            media_type = MediaType.MOVIE
        else:
            media_type = MediaType.ANIME
        tmdb_info = Media().get_tmdb_info(mtype=media_type, tmdbid=tmdbid)
        if not tmdb_info:
            return {"retcode": 1, "retmsg": "??????????????????????????????TMDB??????"}
        # ???????????????
        succ_flag, ret_msg = FileTransfer().transfer_media(in_from=SyncType.MAN,
                                                           in_path=inpath,
                                                           target_dir=outpath,
                                                           tmdb_info=tmdb_info,
                                                           media_type=media_type,
                                                           season=season,
                                                           episode=(
                                                               EpisodeFormat(episode_format, episode_details,
                                                                             episode_offset), False),
                                                           min_filesize=min_filesize,
                                                           udf_flag=True)
        if succ_flag:
            return {"retcode": 0, "retmsg": "????????????"}
        else:
            return {"retcode": 2, "retmsg": ret_msg}

    @staticmethod
    def __delete_history(data):
        """
        ???????????????????????????
        """
        logid = data.get('logid')
        paths = get_transfer_path_by_id(logid)
        if paths:
            dest_dir = paths[0][2]
            meta_info = MetaInfo(title=paths[0][1])
            meta_info.title = paths[0][3]
            meta_info.category = paths[0][4]
            meta_info.year = paths[0][5]
            if paths[0][6]:
                meta_info.begin_season = int(str(paths[0][6]).replace("S", ""))
            if paths[0][7] == MediaType.MOVIE.value:
                meta_info.type = MediaType.MOVIE
            else:
                meta_info.type = MediaType.TV
            dest_path = FileTransfer().get_dest_path_by_info(dest=dest_dir, meta_info=meta_info)
            if dest_path and dest_path.find(meta_info.title) != -1:
                delete_transfer_log_by_id(logid)
                if not meta_info.get_episode_string():
                    # ?????????????????????????????????????????????????????????
                    try:
                        shutil.rmtree(dest_path)
                    except Exception as e:
                        log.console(str(e))
                else:
                    # ?????????????????????
                    for dest_file in get_dir_files(dest_path):
                        file_meta_info = MetaInfo(os.path.basename(dest_file))
                        if file_meta_info.get_episode_list() and set(
                                file_meta_info.get_episode_list()).issubset(set(meta_info.get_episode_list())):
                            try:
                                os.remove(dest_file)
                            except Exception as e:
                                log.console(str(e))
        return {"retcode": 0}

    @staticmethod
    def __logging(data):
        """
        ??????????????????
        """
        if log.LOG_INDEX:
            if log.LOG_INDEX > len(list(log.LOG_QUEUE)):
                text = "<br/>".join(list(log.LOG_QUEUE))
            else:
                text = "<br/>".join(list(log.LOG_QUEUE)[-log.LOG_INDEX:])
            log.LOG_INDEX = 0
            return {"text": text + "<br/>"}
        return {"text": ""}

    def __version(self, data):
        """
        ???????????????
        """
        try:
            response = RequestUtils(proxies=self.config.get_proxies()).get_res(
                "https://api.github.com/repos/jxxghp/nas-tools/releases/latest")
            if response:
                ver_json = response.json()
                version = ver_json["tag_name"]
                info = f'<a href="{ver_json["html_url"]}" target="_blank">{version}</a>'
                return {"code": 0, "version": version, "info": info}
        except Exception as e:
            print(str(e))
        return {"code": -1, "version": "", "info": ""}

    @staticmethod
    def __update_site(data):
        """
        ??????????????????
        """
        tid = data.get('site_id')
        name = data.get('site_name')
        site_pri = data.get('site_pri')
        rssurl = data.get('site_rssurl')
        signurl = data.get('site_signurl')
        cookie = data.get('site_cookie')
        note = data.get('site_note')
        if tid:
            ret = update_config_site(tid=tid,
                                     name=name,
                                     site_pri=site_pri,
                                     rssurl=rssurl,
                                     signurl=signurl,
                                     cookie=cookie,
                                     note=note)
        else:
            ret = insert_config_site(name=name,
                                     site_pri=site_pri,
                                     rssurl=rssurl,
                                     signurl=signurl,
                                     cookie=cookie,
                                     note=note)
        # ??????????????????
        Sites().init_config()
        return {"code": ret}

    @staticmethod
    def __get_site(data):
        """
        ????????????????????????
        """
        tid = data.get("id")
        site_free = False
        site_2xfree = False
        site_hr = False
        if tid:
            ret = Sites().get_sites(siteid=tid)
            if ret.get("rssurl"):
                url_host = parse.urlparse(ret.get("rssurl")).netloc
                if url_host in RSS_SITE_GRAP_CONF.keys():
                    if RSS_SITE_GRAP_CONF[url_host].get("FREE"):
                        site_free = True
                    if RSS_SITE_GRAP_CONF[url_host].get("2XFREE"):
                        site_2xfree = True
                    if RSS_SITE_GRAP_CONF[url_host].get("HR"):
                        site_hr = True
        else:
            ret = []
        return {"code": 0, "site": ret, "site_free": site_free, "site_2xfree": site_2xfree, "site_hr": site_hr}

    @staticmethod
    def __del_site(data):
        """
        ????????????????????????
        """
        tid = data.get("id")
        if tid:
            ret = delete_config_site(tid)
            Sites().init_config()
            return {"code": ret}
        else:
            return {"code": 0}

    def __restart(self, data):
        """
        ??????
        """
        # ????????????
        self.stop_service()
        # ???????????????
        self.shutdown_server()

    def __update_system(self, data):
        """
        ??????
        """
        # ????????????
        self.stop_service()
        # ????????????
        subprocess.call(['pip', 'install', '-r', '/nas-tools/requirements.txt', ])
        # ??????
        subprocess.call(['git', 'pull'])
        # ???????????????
        self.shutdown_server()

    @staticmethod
    def __logout(data):
        """
        ??????
        """
        logout_user()
        return {"code": 0}

    def __update_config(self, data):
        """
        ??????????????????
        """
        cfg = self.config.get_config()
        cfgs = dict(data).items()
        # ??????????????????
        config_test = False
        scheduler_reload = False
        jellyfin_reload = False
        plex_reload = False
        wechat_reload = False
        telegram_reload = False
        category_reload = False
        subtitle_reload = False
        # ????????????
        for key, value in cfgs:
            if key == "test" and value:
                config_test = True
                continue
            # ????????????
            cfg = self.set_config_value(cfg, key, value)
            if key in ['pt.ptsignin_cron', 'pt.pt_monitor', 'pt.pt_check_interval', 'pt.pt_seeding_time',
                       'douban.interval']:
                scheduler_reload = True
            if key.startswith("jellyfin"):
                jellyfin_reload = True
            if key.startswith("plex"):
                plex_reload = True
            if key.startswith("message.telegram"):
                telegram_reload = True
            if key.startswith("message.wechat"):
                wechat_reload = True
            if key.startswith("media.category"):
                category_reload = True
            if key.startswith("subtitle"):
                subtitle_reload = True
        # ????????????
        if not config_test:
            self.config.save_config(cfg)
        # ??????????????????
        if scheduler_reload:
            Scheduler().init_config()
            restart_scheduler()
        # ??????Jellyfin
        if jellyfin_reload:
            Jellyfin().init_config()
        # ??????Plex
        if plex_reload:
            Plex().init_config()
        # ??????wechat
        if wechat_reload:
            WeChat().init_config()
        # ??????telegram
        if telegram_reload:
            Telegram().init_config()
        # ??????????????????
        if category_reload:
            Category().init_config()
        # ????????????
        if subtitle_reload:
            Subtitle().init_config()

        return {"code": 0}

    def __update_directory(self, data):
        """
        ?????????????????????
        """
        cfg = self.set_config_directory(self.config.get_config(), data.get("oper"), data.get("key"),
                                        data.get("value"), data.get("replace_value"))
        # ????????????
        self.config.save_config(cfg)
        if data.get("key") == "sync.sync_path":
            # ????????????
            Sync().init_config()
            # ????????????????????????
            restart_monitor()
        return {"code": 0}

    @staticmethod
    def __remove_rss_media(data):
        """
        ??????RSS??????
        """
        name = data.get("name")
        mtype = data.get("type")
        year = data.get("year")
        season = data.get("season")
        rssid = data.get("rssid")
        page = data.get("page")
        if name:
            meta_info = MetaInfo(title=name)
            name = meta_info.get_name()
            if not season:
                season = meta_info.get_season_string()
        if mtype:
            if mtype in ['nm', 'hm', 'dbom', 'dbhm', 'dbnm', 'MOV']:
                delete_rss_movie(title=name, year=year, rssid=rssid)
            else:
                delete_rss_tv(title=name, year=year, season=season, rssid=rssid)
        return {"code": 0, "page": page, "name": name}

    @staticmethod
    def __add_rss_media(data):
        """
        ??????RSS??????
        """
        doubanid = data.get("doubanid")
        tmdbid = data.get("tmdbid")
        name = data.get("name")
        mtype = data.get("type")
        year = data.get("year")
        season = data.get("season")
        match = data.get("match")
        page = data.get("page")
        sites = data.get("sites")
        search_sites = data.get("search_sites")
        over_edition = data.get("over_edition")
        rss_restype = data.get("rss_restype")
        rss_pix = data.get("rss_pix")
        rss_rule = data.get("rss_rule")
        rssid = data.get("rssid")
        if name and mtype:
            if mtype in ['nm', 'hm', 'dbom', 'dbhm', 'dbnm', 'MOV']:
                mtype = MediaType.MOVIE
            else:
                mtype = MediaType.TV
        code, msg, media_info = add_rss_subscribe(mtype=mtype,
                                                  name=name,
                                                  year=year,
                                                  season=season,
                                                  match=match,
                                                  doubanid=doubanid,
                                                  tmdbid=tmdbid,
                                                  sites=sites,
                                                  search_sites=search_sites,
                                                  over_edition=over_edition,
                                                  rss_restype=rss_restype,
                                                  rss_pix=rss_pix,
                                                  rss_rule=rss_rule,
                                                  rssid=rssid)
        return {"code": code, "msg": msg, "page": page, "name": name}

    @staticmethod
    def __re_identification(data):
        """
        ????????????????????????
        """
        path = dest_dir = None
        unknown_id = data.get("unknown_id")
        if unknown_id:
            paths = get_unknown_path_by_id(unknown_id)
            if paths:
                path = paths[0][0]
                dest_dir = paths[0][1]
            else:
                return {"retcode": -1, "retmsg": "???????????????????????????"}
        if not dest_dir:
            dest_dir = ""
        if not path:
            return {"retcode": -1, "retmsg": "?????????????????????"}
        succ_flag, ret_msg = FileTransfer().transfer_media(in_from=SyncType.MAN,
                                                           in_path=path,
                                                           target_dir=dest_dir)
        if succ_flag:
            update_transfer_unknown_state(path)
            return {"retcode": 0, "retmsg": "????????????"}
        else:
            return {"retcode": 2, "retmsg": ret_msg}

    @staticmethod
    def __media_info(data):
        """
        ??????????????????
        """
        tmdbid = data.get("id")
        mtype = data.get("type")
        title = data.get("title")
        year = data.get("year")
        page = data.get("page")
        doubanid = data.get("doubanid")
        rssid = data.get("rssid")
        if mtype in ['hm', 'nm', 'dbom', 'dbhm', 'dbnm', 'MOV']:
            media_type = MediaType.MOVIE
        else:
            media_type = MediaType.TV

        if media_type == MediaType.MOVIE:
            # ???????????????
            if doubanid:
                link_url = "https://movie.douban.com/subject/%s" % doubanid
                douban_info = DoubanApi().movie_detail(doubanid)
                if not douban_info or douban_info.get("localized_message"):
                    return {"code": 1, "retmsg": "???????????????????????????", "link_url": link_url}
                overview = douban_info.get("intro")
                poster_path = douban_info.get("cover_url")
                title = douban_info.get("title")
                vote_average = douban_info.get("rating", {}).get("value") or ""
                release_date = douban_info.get("pubdate")
                year = douban_info.get("year")
            else:
                link_url = "https://www.themoviedb.org/movie/%s" % tmdbid
                tmdb_info = Media().get_tmdb_info(media_type, title, year, tmdbid)
                if not tmdb_info:
                    return {"code": 1, "retmsg": "???????????????TMDB??????", "link_url": link_url}
                overview = tmdb_info.get("overview")
                poster_path = "https://image.tmdb.org/t/p/w500%s" % tmdb_info.get('poster_path') if tmdb_info.get(
                    'poster_path') else ""
                title = tmdb_info.get('title')
                vote_average = tmdb_info.get("vote_average")
                release_date = tmdb_info.get('release_date')
                year = release_date[0:4] if release_date else ""

            # ???????????????
            if not rssid:
                rssid = get_rss_movie_id(title=title, year=year)

            # ???????????????

            return {
                "code": 0,
                "type": mtype,
                "type_str": media_type.value,
                "page": page,
                "title": title,
                "vote_average": vote_average,
                "poster_path": poster_path,
                "release_date": release_date,
                "year": year,
                "overview": overview,
                "link_url": link_url,
                "tmdbid": tmdbid,
                "doubanid": doubanid,
                "rssid": rssid
            }
        else:
            # ???????????????
            if doubanid:
                link_url = "https://movie.douban.com/subject/%s" % doubanid
                douban_info = DoubanApi().tv_detail(doubanid)
                if not douban_info or douban_info.get("localized_message"):
                    return {"code": 1, "retmsg": "???????????????????????????", "link_url": link_url}
                overview = douban_info.get("intro")
                poster_path = douban_info.get("cover_url")
                title = douban_info.get("title")
                vote_average = douban_info.get("rating", {}).get("value") or ""
                release_date = douban_info.get("pubdate")
                year = douban_info.get("year")
            else:
                link_url = "https://www.themoviedb.org/tv/%s" % tmdbid
                tmdb_info = Media().get_tmdb_info(media_type, title, year, tmdbid)
                if not tmdb_info:
                    return {"code": 1, "retmsg": "???????????????TMDB??????", "link_url": link_url}
                overview = tmdb_info.get("overview")
                poster_path = "https://image.tmdb.org/t/p/w500%s" % tmdb_info.get('poster_path') if tmdb_info.get(
                    'poster_path') else ""
                title = tmdb_info.get('name')
                vote_average = tmdb_info.get("vote_average")
                release_date = tmdb_info.get('first_air_date')
                year = release_date[0:4] if release_date else ""

            # ???????????????
            if not rssid:
                rssid = get_rss_tv_id(title=title, year=year)

            return {
                "code": 0,
                "type": mtype,
                "type_str": media_type.value,
                "page": page,
                "title": title,
                "vote_average": vote_average,
                "poster_path": poster_path,
                "release_date": release_date,
                "year": year,
                "overview": overview,
                "link_url": link_url,
                "tmdbid": tmdbid,
                "doubanid": doubanid,
                "rssid": rssid
            }

    def __test_connection(self, data):
        """
        ???????????????
        """
        # ????????????????????????????????????????????????????????????????????????xx|xx????????????????????????????????????????????????
        command = data.get("command")
        ret = None
        if command:
            try:
                if isinstance(command, list):
                    for cmd_str in command:
                        ret = eval(cmd_str)
                        if not ret:
                            break
                else:
                    if command.find("|") != -1:
                        module = command.split("|")[0]
                        class_name = command.split("|")[1]
                        ret = getattr(importlib.import_module(module), class_name)().get_status()
                    else:
                        ret = eval(command)
                # ????????????
                self.config.init_config()
            except Exception as e:
                ret = None
                print(str(e))
            return {"code": 0 if ret else 1}
        return {"code": 0}

    @staticmethod
    def __user_manager(data):
        """
        ????????????
        """
        oper = data.get("oper")
        name = data.get("name")
        if oper == "add":
            password = generate_password_hash(str(data.get("password")))
            pris = data.get("pris")
            if isinstance(pris, list):
                pris = ",".join(pris)
            ret = insert_user(name, password, pris)
        else:
            ret = delete_user(name)
        return {"code": ret}

    @staticmethod
    def __refresh_rss(data):
        """
        ????????????RSS
        """
        mtype = data.get("type")
        rssid = data.get("rssid")
        page = data.get("page")
        if mtype == "MOV":
            ThreadHelper().start_thread(Rss().rsssearch_movie, (rssid,))
        else:
            ThreadHelper().start_thread(Rss().rsssearch_tv, (rssid,))
        return {"code": 0, "page": page}

    @staticmethod
    def __refresh_message(data):
        """
        ????????????????????????
        """
        lst_time = data.get("lst_time")
        messages = MessageCenter().get_system_messages(lst_time=lst_time)
        message_html = []
        for message in list(reversed(messages)):
            lst_time = message.get("time")
            level = "bg-red" if message.get("level") == "ERROR" else ""
            content = re.sub(r"[#]+", "<br>",
                             re.sub(r"<[^>]+>", "",
                                    re.sub(r"<br/?>", "####", message.get("content"), flags=re.IGNORECASE)))
            message_html.append(f"""
            <div class="list-group-item">
              <div class="row align-items-center">
                <div class="col-auto">
                  <span class="status-dot {level} d-block"></span>
                </div>
                <div class="col text-truncate">
                  <span class="text-wrap">{message.get("title")}</span>
                  <div class="d-block text-muted text-truncate mt-n1 text-wrap">{content}</div>
                  <div class="d-block text-muted text-truncate mt-n1 text-wrap">{message.get("time")}</div>
                </div>
              </div>
            </div>
            """)
        return {"code": 0, "message": message_html, "lst_time": lst_time}

    @staticmethod
    def __delete_tmdb_cache(data):
        """
        ??????tmdb??????
        """
        if MetaHelper().delete_meta_data(data.get("cache_key")):
            MetaHelper().save_meta_data()
        return {"code": 0}

    @staticmethod
    def __movie_calendar_data(data):
        """
        ????????????????????????
        """
        tid = data.get("id")
        if tid and tid.startswith("DB:"):
            doubanid = tid.replace("DB:", "")
            douban_info = DoubanApi().movie_detail(doubanid)
            if not douban_info:
                return {"code": 1, "retmsg": "???????????????????????????"}
            poster_path = douban_info.get("cover_url") or ""
            title = douban_info.get("title")
            vote_average = douban_info.get("rating", {}).get("value") or "???"
            release_date = re.sub(r"\(.*\)", "", douban_info.get("pubdate")[0])
            if not release_date:
                return {"code": 1, "retmsg": "?????????????????????"}
            else:
                return {"code": 0,
                        "type": "??????",
                        "title": title,
                        "start": release_date,
                        "id": tid,
                        "year": release_date[0:4] if release_date else "",
                        "poster": poster_path,
                        "vote_average": vote_average
                        }
        else:
            tmdb_info = Media().get_tmdb_info(mtype=MediaType.MOVIE, tmdbid=tid)
            if not tmdb_info:
                return {"code": 1, "retmsg": "???????????????TMDB??????"}
            poster_path = "https://image.tmdb.org/t/p/w500%s" % tmdb_info.get('poster_path') if tmdb_info.get(
                'poster_path') else ""
            title = tmdb_info.get('title')
            vote_average = tmdb_info.get("vote_average")
            release_date = tmdb_info.get('release_date')
            if not release_date:
                return {"code": 1, "retmsg": "?????????????????????"}
            else:
                return {"code": 0,
                        "type": "??????",
                        "title": title,
                        "start": release_date,
                        "id": tid,
                        "year": release_date[0:4] if release_date else "",
                        "poster": poster_path,
                        "vote_average": vote_average
                        }

    @staticmethod
    def __tv_calendar_data(data):
        """
        ???????????????????????????
        """
        tid = data.get("id")
        season = data.get("season")
        name = data.get("name")
        if tid and tid.startswith("DB:"):
            doubanid = tid.replace("DB:", "")
            douban_info = DoubanApi().tv_detail(doubanid)
            if not douban_info:
                return {"code": 1, "retmsg": "???????????????????????????"}
            poster_path = douban_info.get("cover_url") or ""
            title = douban_info.get("title")
            vote_average = douban_info.get("rating", {}).get("value") or "???"
            release_date = re.sub(r"\(.*\)", "", douban_info.get("pubdate")[0])
            if not release_date:
                return {"code": 1, "retmsg": "?????????????????????"}
            else:
                return {"code": 0,
                        "type": "?????????",
                        "title": title,
                        "start": release_date,
                        "id": tid,
                        "year": release_date[0:4] if release_date else "",
                        "poster": poster_path,
                        "vote_average": vote_average
                        }
        else:
            tmdb_info = Media().get_tmdb_tv_season_detail(tmdbid=tid, season=season)
            if not tmdb_info:
                return {"code": 1, "retmsg": "???????????????TMDB??????"}
            episode_events = []
            air_date = tmdb_info.get("air_date")
            if not tmdb_info.get("poster_path"):
                tv_tmdb_info = Media().get_tmdb_info(mtype=MediaType.TV, tmdbid=tid)
                if tv_tmdb_info:
                    poster_path = "https://image.tmdb.org/t/p/w500%s" % tv_tmdb_info.get("poster_path")
                else:
                    poster_path = ""
            else:
                poster_path = "https://image.tmdb.org/t/p/w500%s" % tmdb_info.get("poster_path")
            year = air_date[0:4] if air_date else ""
            for episode in tmdb_info.get("episodes"):
                episode_events.append({
                    "type": "??????",
                    "title": "%s ???%s??????%s???" % (
                        name, season, episode.get("episode_number")) if season != 1 else "%s ???%s???" % (
                        name, episode.get("episode_number")),
                    "start": episode.get("air_date"),
                    "id": tid,
                    "year": year,
                    "poster": poster_path,
                    "vote_average": episode.get("vote_average") or "???"
                })
            return {"code": 0, "events": episode_events}

    @staticmethod
    def __rss_detail(data):
        rssid = data.get("rssid")
        rsstype = data.get("rsstype")
        if rsstype == "MOV":
            rss = get_rss_movies(rssid=rssid)
            if not rss:
                return {"code": 1}
            r_sites, s_sites, over_edition, filter_map = Torrent.get_rss_note_item(rss[0][4])
            rssdetail = {"rssid": rssid,
                         "name": rss[0][0],
                         "year": rss[0][1],
                         "tmdbid": rss[0][2],
                         "r_sites": r_sites,
                         "s_sites": s_sites,
                         "over_edition": over_edition,
                         "filter": filter_map}
        else:
            rss = get_rss_tvs(rssid=rssid)
            if not rss:
                return {"code": 1}
            r_sites, s_sites, over_edition, filter_map = Torrent.get_rss_note_item(rss[0][5])
            rssdetail = {"rssid": rssid,
                         "name": rss[0][0],
                         "year": rss[0][1],
                         "season": rss[0][2],
                         "tmdbid": rss[0][3],
                         "r_sites": r_sites,
                         "s_sites": s_sites,
                         "over_edition": over_edition,
                         "filter": filter_map}

        return {"code": 0, "detail": rssdetail}

    @staticmethod
    def __modify_tmdb_cache(data):
        """
        ??????TMDB???????????????
        """
        if MetaHelper().modify_meta_data(data.get("key"), data.get("title")):
            MetaHelper().save_meta_data(force=True)
        return {"code": 0}

    @staticmethod
    def __truncate_blacklist(data):
        """
        ?????????????????????????????????
        """
        return {"code": truncate_transfer_blacklist()}

    @staticmethod
    def __add_brushtask(data):
        """
        ??????????????????
        """
        # ?????????
        brushtask_id = data.get("brushtask_id")
        brushtask_name = data.get("brushtask_name")
        brushtask_site = data.get("brushtask_site")
        brushtask_interval = data.get("brushtask_interval")
        brushtask_downloader = data.get("brushtask_downloader")
        brushtask_totalsize = data.get("brushtask_totalsize")
        brushtask_state = data.get("brushtask_state")
        brushtask_transfer = 'Y' if data.get("brushtask_transfer") else 'N'
        brushtask_free = data.get("brushtask_free")
        brushtask_hr = data.get("brushtask_hr")
        brushtask_torrent_size = data.get("brushtask_torrent_size")
        brushtask_include = data.get("brushtask_include")
        brushtask_exclude = data.get("brushtask_exclude")
        brushtask_dlcount = data.get("brushtask_dlcount")
        brushtask_seedtime = data.get("brushtask_seedtime")
        brushtask_seedratio = data.get("brushtask_seedratio")
        brushtask_seedsize = data.get("brushtask_seedsize")
        brushtask_dltime = data.get("brushtask_dltime")
        brushtask_avg_upspeed = data.get("brushtask_avg_upspeed")
        # ????????????
        rss_rule = {
            "free": brushtask_free,
            "hr": brushtask_hr,
            "size": brushtask_torrent_size,
            "include": brushtask_include,
            "exclude": brushtask_exclude,
            "dlcount": brushtask_dlcount
        }
        # ????????????
        remove_rule = {
            "time": brushtask_seedtime,
            "ratio": brushtask_seedratio,
            "uploadsize": brushtask_seedsize,
            "dltime": brushtask_dltime,
            "avg_upspeed": brushtask_avg_upspeed
        }
        # ????????????
        item = {
            "name": brushtask_name,
            "site": brushtask_site,
            "free": brushtask_free,
            "interval": brushtask_interval,
            "downloader": brushtask_downloader,
            "seed_size": brushtask_totalsize,
            "transfer": brushtask_transfer,
            "state": brushtask_state,
            "rss_rule": rss_rule,
            "remove_rule": remove_rule
        }
        insert_brushtask(brushtask_id, item)
        # ?????????????????????
        BrushTask().init_config()
        return {"code": 0}

    @staticmethod
    def __del_brushtask(data):
        """
        ??????????????????
        """
        brush_id = data.get("id")
        if brush_id:
            delete_brushtask(brush_id)
            # ?????????????????????
            BrushTask().init_config()
            return {"code": 0}
        return {"code": 1}

    @staticmethod
    def __brushtask_detail(data):
        """
        ????????????????????????
        """
        brush_id = data.get("id")
        brushtask = get_brushtasks(brush_id)
        if not brushtask:
            return {"code": 1, "task": {}}
        task = {
            "id": brushtask[0][0],
            "name": brushtask[0][1],
            "site": brushtask[0][2],
            "interval": brushtask[0][4],
            "state": brushtask[0][5],
            "downloader": brushtask[0][6],
            "transfer": brushtask[0][7],
            "free": brushtask[0][8],
            "rss_rule": eval(brushtask[0][9]),
            "remove_rule": eval(brushtask[0][10]),
            "seed_size": brushtask[0][11],
            "download_count": brushtask[0][12],
            "remove_count": brushtask[0][13],
            "download_size": str_filesize(brushtask[0][14]),
            "upload_size": str_filesize(brushtask[0][15]),
            "lst_mod_date": brushtask[0][16],
            "site_url": "http://%s" % parse.urlparse(brushtask[0][17]).netloc if brushtask[0][17] else ""
        }
        return {"code": 0, "task": task}

    @staticmethod
    def __add_downloader(data):
        """
        ????????????????????????
        """
        test = data.get("test")
        dl_name = data.get("name")
        dl_type = data.get("type")
        user_config = {"host": data.get("host"),
                       "port": data.get("port"),
                       "username": data.get("username"),
                       "password": data.get("password"),
                       "save_dir": data.get("save_dir")}
        if test:
            # ??????
            if dl_type == "qbittorrent":
                downloader = Qbittorrent(user_config=user_config)
            else:
                downloader = Transmission(user_config=user_config)
            if downloader.get_status():
                return {"code": 0}
            else:
                return {"code": 1}
        else:
            # ??????
            insert_user_downloader(name=dl_name, dtype=dl_type, user_config=user_config, note=None)
            return {"code": 0}

    @staticmethod
    def __delete_downloader(data):
        """
        ????????????????????????
        """
        dl_id = data.get("id")
        if dl_id:
            delete_user_downloader(dl_id)
        return {"code": 0}

    @staticmethod
    def __name_test(data):
        """
        ??????????????????
        """
        name = data.get("name")
        if not name:
            return {"code": -1}
        media_info = Media().get_media_info(title=name)
        return {"code": 0, "data": {
            "type": media_info.type.value,
            "name": media_info.get_name(),
            "title": media_info.title,
            "year": media_info.year,
            "season_episode": media_info.get_season_episode_string(),
            "part": media_info.part,
            "tmdbid": media_info.tmdb_id,
            "category": media_info.category,
            "restype": media_info.resource_type,
            "pix": media_info.resource_pix,
            "video_codec": media_info.video_encode,
            "audio_codec": media_info.audio_encode
        }}

    @staticmethod
    def __rule_test(data):
        title = data.get("title")
        subtitle = data.get("subtitle")
        size = data.get("size")
        if size:
            size = float(size) * 1024 ** 3
        if not title:
            return {"code": -1}
        meta_info = MetaInfo(title=title, subtitle=subtitle)
        match_flag, res_order, rule_name = FilterRule().check_rules(meta_info=meta_info,
                                                                    torrent_size=size)
        return {
            "code": 0,
            "flag": match_flag,
            "text": "??????" if match_flag else "?????????",
            "name": rule_name if rule_name else "?????????????????????",
            "order": 100 - res_order if res_order else 0
        }

    @staticmethod
    def __get_site_activity(data):
        """
        ??????site??????[???????????????????????????]
        :param data: {"name":site_name}
        :return:
        """
        if not data or "name" not in data:
            return {"code": 1, "msg": "??????????????????"}

        resp = {"code": 0}
        resp.update(Sites().get_pt_site_activity_history(data["name"]))
        return resp

    @staticmethod
    def __get_site_history(data):
        """
        ??????site ??????[???????????????]
        :param data: {"days":????????????}
        :return:
        """
        if not data or "days" not in data or not isinstance(data["days"], int):
            return {"code": 1, "msg": "??????????????????"}

        resp = {"code": 0}
        _, _, site, upload, download = Sites().get_pt_site_statistics_history(data["days"]+1)
        resp.update({"site": site, "upload": upload, "download": download})
        return resp

    @staticmethod
    def __get_site_seeding_info(data):
        """
        ??????site ?????????????????? ??????????????????
        :param data: {"name":site_name}
        :return:
        """
        if not data or "name" not in data:
            return {"code": 1, "msg": "??????????????????"}

        resp = {"code": 0}
        resp.update(Sites().get_pt_site_seeding_info(data["name"]))
        return resp

    @staticmethod
    def __add_filtergroup(data):
        """
        ???????????????
        """
        name = data.get("name")
        default = data.get("default")
        if not name:
            return {"code": -1}
        add_filter_group(name, default)
        FilterRule().init_config()
        return {"code": 0}

    @staticmethod
    def __set_default_filtergroup(data):
        groupid = data.get("id")
        if not groupid:
            return {"code": -1}
        set_default_filtergroup(groupid)
        FilterRule().init_config()
        return {"code": 0}

    @staticmethod
    def __del_filtergroup(data):
        groupid = data.get("id")
        delete_filtergroup(groupid)
        FilterRule().init_config()
        return {"code": 0}

    @staticmethod
    def __add_filterrule(data):
        rule_id = data.get("rule_id")
        item = {
            "group": data.get("group_id"),
            "name": data.get("rule_name"),
            "pri": data.get("rule_pri"),
            "include": data.get("rule_include"),
            "exclude": data.get("rule_exclude"),
            "size": data.get("rule_sizelimit")
        }
        insert_filter_rule(rule_id, item)
        FilterRule().init_config()
        return {"code": 0}

    @staticmethod
    def __del_filterrule(data):
        ruleid = data.get("id")
        delete_filterrule(ruleid)
        FilterRule().init_config()
        return {"code": 0}

    @staticmethod
    def __filterrule_detail(data):
        rid = data.get("ruleid")
        groupid = data.get("groupid")
        ruleinfo = FilterRule().get_rules(groupid=groupid, ruleid=rid)
        if ruleinfo:
            ruleinfo['include'] = "\n".join(ruleinfo.get("include"))
            ruleinfo['exclude'] = "\n".join(ruleinfo.get("exclude"))
        return {"code": 0, "info": ruleinfo}

    @staticmethod
    def get_recommend(data):
        RecommendType = data.get("type")
        CurrentPage = data.get("page")
        if not CurrentPage:
            CurrentPage = 1
        else:
            CurrentPage = int(CurrentPage)
        if RecommendType == "hm":
            # TMDB????????????
            res_list = Media().get_tmdb_hot_movies(CurrentPage)
        elif RecommendType == "ht":
            # TMDB???????????????
            res_list = Media().get_tmdb_hot_tvs(CurrentPage)
        elif RecommendType == "nm":
            # TMDB????????????
            res_list = Media().get_tmdb_new_movies(CurrentPage)
        elif RecommendType == "nt":
            # TMDB???????????????
            res_list = Media().get_tmdb_new_tvs(CurrentPage)
        elif RecommendType == "dbom":
            # ??????????????????
            res_list = DoubanHot().get_douban_online_movie(CurrentPage)
        elif RecommendType == "dbhm":
            # ??????????????????
            res_list = DoubanHot().get_douban_hot_movie(CurrentPage)
        elif RecommendType == "dbht":
            # ?????????????????????
            res_list = DoubanHot().get_douban_hot_tv(CurrentPage)
        elif RecommendType == "dbdh":
            # ??????????????????
            res_list = DoubanHot().get_douban_hot_anime(CurrentPage)
        elif RecommendType == "dbnm":
            # ??????????????????
            res_list = DoubanHot().get_douban_new_movie(CurrentPage)
        elif RecommendType == "dbzy":
            # ?????????????????????
            res_list = DoubanHot().get_douban_hot_show(CurrentPage)
        else:
            res_list = []

        Items = []
        TvKeys = ["%s" % key[0] for key in get_rss_tvs()]
        MovieKeys = ["%s" % key[0] for key in get_rss_movies()]
        for res in res_list:
            rid = res.get('id')
            if RecommendType in ['hm', 'nm', 'dbom', 'dbhm', 'dbnm']:
                title = res.get('title')
                date = res.get('release_date')
                if date:
                    year = date[0:4]
                else:
                    year = ''
                if title in MovieKeys:
                    # ?????????
                    fav = 1
                elif is_media_downloaded(title, year):
                    # ?????????
                    fav = 2
                else:
                    # ?????????????????????
                    fav = 0
            else:
                title = res.get('name')
                date = res.get('first_air_date')
                if date:
                    year = date[0:4]
                else:
                    year = ''
                if MetaInfo(title=title).get_name() in TvKeys:
                    # ?????????
                    fav = 1
                elif is_media_downloaded(MetaInfo(title=title).get_name(), year):
                    # ?????????
                    fav = 2
                else:
                    # ?????????????????????
                    fav = 0
            image = res.get('poster_path')
            if RecommendType in ['hm', 'nm', 'ht', 'nt']:
                image = "https://image.tmdb.org/t/p/original/%s" % image if image else ""
            else:
                # ?????????????????????
                image = image.replace("s_ratio_poster", "m_ratio_poster")
            vote = res.get('vote_average')
            overview = res.get('overview')
            item = {'id': rid,
                    'title': title,
                    'fav': fav,
                    'date': date,
                    'vote': vote,
                    'image': image,
                    'overview': overview,
                    'year': year}
            Items.append(item)
        return {"code": 0, "Items": Items}

    @staticmethod
    def get_downloaded(data):
        page = data.get("page")
        Items = get_download_history(page=page) or []
        return {"code": 0, "Items": Items}

    @staticmethod
    def parse_sites_string(notes):
        if not notes:
            return ""
        rss_sites, search_sites, _, _ = Torrent.get_rss_note_item(notes)
        rss_site_htmls = ['<span class="badge bg-lime me-1 mb-1" title="????????????">%s</span>' % s for s in
                          rss_sites if s]
        search_site_htmls = ['<span class="badge bg-yellow me-1 mb-1" title="????????????">%s</span>' % s for s in
                             search_sites if s]

        return "".join(rss_site_htmls) + "".join(search_site_htmls)

    @staticmethod
    def parse_filter_string(notes):
        if not notes:
            return ""
        _, _, over_edition, filter_map = Torrent.get_rss_note_item(notes)
        filter_htmls = []
        if over_edition:
            filter_htmls.append('<span class="badge badge-outline text-red me-1 mb-1" title="???????????????">??????</span>')
        if filter_map.get("restype"):
            filter_htmls.append(
                '<span class="badge badge-outline text-orange me-1 mb-1">%s</span>' % filter_map.get("restype"))
        if filter_map.get("pix"):
            filter_htmls.append(
                '<span class="badge badge-outline text-orange me-1 mb-1">%s</span>' % filter_map.get("pix"))
        if filter_map.get("rule"):
            filter_htmls.append('<span class="badge badge-outline text-orange me-1 mb-1">%s</span>' %
                                FilterRule().get_rule_groups(groupid=filter_map.get("rule")).get("name") or "")
        return "".join(filter_htmls)

    @staticmethod
    def parse_brush_rule_string(rules: dict):
        if not rules:
            return ""
        rule_filter_string = {"gt": "??????", "lt": "??????", "bw": "??????"}
        rule_htmls = []
        if rules.get("size"):
            sizes = rules.get("size").split("#")
            if sizes[0]:
                if sizes[1]:
                    sizes[1] = sizes[1].replace(",", "-")
                rule_htmls.append('<span class="badge badge-outline text-blue me-1 mb-1" title="????????????">%s: %s GB</span>'
                                  % (rule_filter_string.get(sizes[0]), sizes[1]))
        if rules.get("include"):
            rule_htmls.append('<span class="badge badge-outline text-green me-1 mb-1" title="????????????">??????: %s</span>'
                              % rules.get("include"))
        if rules.get("hr"):
            rule_htmls.append('<span class="badge badge-outline text-red me-1 mb-1" title="??????HR">??????: HR</span>')
        if rules.get("exclude"):
            rule_htmls.append('<span class="badge badge-outline text-red me-1 mb-1" title="????????????">??????: %s</span>'
                              % rules.get("exclude"))
        if rules.get("dlcount"):
            rule_htmls.append('<span class="badge badge-outline text-orange me-1 mb-1" title="????????????????????????">????????????: %s</span>'
                              % rules.get("dlcount"))
        if rules.get("time"):
            times = rules.get("time").split("#")
            if times[0]:
                rule_htmls.append(
                    '<span class="badge badge-outline text-orange me-1 mb-1" title="????????????">??????%s: %s ??????</span>'
                    % (rule_filter_string.get(times[0]), times[1]))
        if rules.get("ratio"):
            ratios = rules.get("ratio").split("#")
            if ratios[0]:
                rule_htmls.append('<span class="badge badge-outline text-orange me-1 mb-1" title="?????????">?????????%s: %s</span>'
                                  % (rule_filter_string.get(ratios[0]), ratios[1]))
        if rules.get("uploadsize"):
            uploadsizes = rules.get("uploadsize").split("#")
            if uploadsizes[0]:
                rule_htmls.append(
                    '<span class="badge badge-outline text-orange me-1 mb-1" title="?????????">?????????%s: %s GB</span>'
                    % (rule_filter_string.get(uploadsizes[0]), uploadsizes[1]))
        if rules.get("dltime"):
            dltimes = rules.get("dltime").split("#")
            if dltimes[0]:
                rule_htmls.append(
                    '<span class="badge badge-outline text-orange me-1 mb-1" title="????????????">????????????%s: %s ??????</span>'
                    % (rule_filter_string.get(dltimes[0]), dltimes[1]))
        if rules.get("avg_upspeed"):
            avg_upspeeds = rules.get("avg_upspeed").split("#")
            if avg_upspeeds[0]:
                rule_htmls.append(
                    '<span class="badge badge-outline text-orange me-1 mb-1" title="??????????????????">??????????????????%s: %s KB/S</span>'
                    % (rule_filter_string.get(avg_upspeeds[0]), avg_upspeeds[1]))

        return "<br>".join(rule_htmls)

    @staticmethod
    def __clear_tmdb_cache(data):
        """
        ??????TMDB??????
        """
        try:
            MetaHelper().clear_meta_data()
            os.remove(MetaHelper().get_meta_data_path())
        except Exception as e:
            return {"code": 0, "msg": str(e)}
        return {"code": 0}

    @staticmethod
    def __check_site_attr(data):
        """
        ??????????????????
        """
        url = data.get("url")
        url_host = parse.urlparse(url).netloc
        site_free = site_2xfree = site_hr = False
        if url_host in RSS_SITE_GRAP_CONF.keys():
            if RSS_SITE_GRAP_CONF[url_host].get("FREE"):
                site_free = True
            if RSS_SITE_GRAP_CONF[url_host].get("2XFREE"):
                site_2xfree = True
            if RSS_SITE_GRAP_CONF[url_host].get("HR"):
                site_hr = True
        return {"code": 0, "site_free": site_free, "site_2xfree": site_2xfree, "site_hr": site_hr}

    @staticmethod
    def __refresh_process(data):
        """
        ???????????????
        """
        detail = ProcessHandler().get_process()
        if detail:
            return {"code": 0, "value": detail.get("value"), "text": detail.get("text")}
        else:
            return {"code": 1}
