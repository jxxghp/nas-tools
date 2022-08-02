import datetime
import os.path
import time
from enum import Enum

from rmt.meta.metabase import MetaBase
from utils.db_helper import update_by_sql, select_by_sql, update_by_sql_batch
from utils.functions import str_filesize, xstr, str_sql
from utils.types import MediaType, RmtMode


# 将返回信息插入数据库
def insert_search_results(media_items: list):
    if not media_items:
        return
    sql = "INSERT INTO SEARCH_RESULT_INFO(" \
          "TORRENT_NAME," \
          "ENCLOSURE," \
          "DESCRIPTION," \
          "TYPE," \
          "TITLE," \
          "YEAR," \
          "SEASON," \
          "EPISODE," \
          "ES_STRING," \
          "VOTE," \
          "IMAGE," \
          "POSTER," \
          "TMDBID," \
          "OVERVIEW," \
          "RES_TYPE," \
          "RES_ORDER," \
          "SIZE," \
          "SEEDERS," \
          "PEERS," \
          "SITE," \
          "SITE_ORDER," \
          "PAGEURL," \
          "UPLOAD_VOLUME_FACTOR," \
          "DOWNLOAD_VOLUME_FACTOR) VALUES (" \
          " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    data_list = []
    for media_item in media_items:
        if media_item.type == MediaType.TV:
            mtype = "TV"
        elif media_item.type == MediaType.MOVIE:
            mtype = "MOV"
        else:
            mtype = "ANI"
        data_list.append(
            (
                str_sql(media_item.org_string),
                str_sql(media_item.enclosure),
                str_sql(media_item.description),
                mtype,
                str_sql(media_item.title) or str_sql(media_item.get_name()),
                xstr(media_item.year),
                media_item.get_season_string(),
                media_item.get_episode_string(),
                media_item.get_season_episode_string(),
                media_item.vote_average or "0",
                media_item.get_backdrop_path(default=False),
                media_item.get_poster_image(),
                str_sql(media_item.tmdb_id),
                str_sql(media_item.overview),
                media_item.get_resource_type_string(),
                media_item.res_order,
                str_filesize(int(media_item.size)),
                media_item.seeders,
                media_item.peers,
                media_item.site,
                media_item.site_order,
                str_sql(media_item.page_url),
                media_item.upload_volume_factor,
                media_item.download_volume_factor
            )
        )
    return update_by_sql_batch(sql, data_list)


# 根据ID从数据库中查询检索结果的一条记录
def get_search_result_by_id(dl_id):
    sql = "SELECT ENCLOSURE,TITLE,YEAR,SEASON,EPISODE,VOTE,IMAGE,TYPE,TORRENT_NAME,DESCRIPTION,SIZE,TMDBID,POSTER,OVERVIEW,SITE,UPLOAD_VOLUME_FACTOR,DOWNLOAD_VOLUME_FACTOR" \
          " FROM SEARCH_RESULT_INFO" \
          " WHERE ID = ?"
    return select_by_sql(sql, (dl_id,))


# 查询检索结果的所有记录
def get_search_results():
    sql = "SELECT ID,TITLE||' ('||YEAR||') '||ES_STRING,RES_TYPE,SIZE,SEEDERS," \
          "ENCLOSURE,SITE,YEAR,ES_STRING,IMAGE,TYPE,VOTE*1,TORRENT_NAME,DESCRIPTION,TMDBID,POSTER,OVERVIEW,PAGEURL,OTHERINFO,UPLOAD_VOLUME_FACTOR,DOWNLOAD_VOLUME_FACTOR" \
          " FROM SEARCH_RESULT_INFO"
    return select_by_sql(sql)


# 查询RSS是否处理过，根据名称
def is_torrent_rssd(enclosure):
    if not enclosure:
        return True
    sql = "SELECT COUNT(1) FROM RSS_TORRENTS WHERE ENCLOSURE = ?"
    rets = select_by_sql(sql, (enclosure,))
    if rets and rets[0][0] > 0:
        return True
    else:
        return False


# 删除所有搜索的记录
def delete_all_search_torrents():
    return update_by_sql("DELETE FROM SEARCH_RESULT_INFO")


# 将RSS的记录插入数据库
def insert_rss_torrents(media_info: MetaBase):
    sql = "INSERT INTO RSS_TORRENTS(TORRENT_NAME, ENCLOSURE, TYPE, TITLE, YEAR, SEASON, EPISODE) " \
          "VALUES (?, ?, ?, ?, ?, ?, ?)"
    return update_by_sql(sql, (str_sql(media_info.org_string),
                               media_info.enclosure,
                               media_info.type.value,
                               str_sql(media_info.title),
                               str_sql(media_info.year),
                               media_info.get_season_string(),
                               media_info.get_episode_string()))


# 将豆瓣的数据插入数据库
def insert_douban_media_state(media: MetaBase, state):
    if not media.year:
        sql = "DELETE FROM DOUBAN_MEDIAS WHERE NAME = ?"
        update_by_sql(sql, (str_sql(media.get_name()),))
    else:
        sql = "DELETE FROM DOUBAN_MEDIAS WHERE NAME = ? AND YEAR = ?"
        update_by_sql(sql, (str_sql(media.get_name()), str_sql(media.year)))

    sql = "INSERT INTO DOUBAN_MEDIAS(NAME, YEAR, TYPE, RATING, IMAGE, STATE) VALUES (?, ?, ?, ?, ?, ?)"
    # 再插入
    return update_by_sql(sql, (str_sql(media.get_name()),
                               str_sql(media.year),
                               media.type.value,
                               media.vote_average,
                               media.get_poster_image(),
                               state))


# 标记豆瓣数据的状态
def update_douban_media_state(media: MetaBase, state):
    sql = "UPDATE DOUBAN_MEDIAS SET STATE = ? WHERE NAME = ? AND YEAR = ?"
    return update_by_sql(sql, (state, str_sql(media.title), str_sql(media.year)))


# 查询未检索的豆瓣数据
def get_douban_search_state(title, year):
    sql = "SELECT STATE FROM DOUBAN_MEDIAS WHERE NAME = ? AND YEAR = ?"
    return select_by_sql(sql, (str_sql(title), str_sql(year)))


# 查询识别转移记录
def is_transfer_history_exists(file_path, file_name, title, se):
    if not file_path:
        return False
    sql = "SELECT COUNT(1) FROM TRANSFER_HISTORY WHERE FILE_PATH = ? AND FILE_NAME = ? AND TITLE = ? AND SE = ?"
    ret = select_by_sql(sql, (str_sql(file_path), str_sql(file_name), str_sql(title), str_sql(se)))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 插入识别转移记录
def insert_transfer_history(in_from: Enum, rmt_mode: RmtMode, in_path, dest, media_info: MetaBase):
    if not media_info or not media_info.tmdb_info:
        return
    if in_path:
        in_path = os.path.normpath(in_path)
    else:
        return False
    if not dest:
        dest = ""
    file_path = os.path.dirname(in_path)
    file_name = os.path.basename(in_path)
    if is_transfer_history_exists(file_path, file_name, media_info.title, media_info.get_season_string()):
        return True
    timestr = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    sql = "INSERT INTO TRANSFER_HISTORY" \
          "(SOURCE, MODE, TYPE, FILE_PATH, FILE_NAME, TITLE, CATEGORY, YEAR, SE, DEST, DATE)" \
          " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    return update_by_sql(sql, (in_from.value,
                               rmt_mode.value,
                               media_info.type.value,
                               str_sql(file_path),
                               str_sql(file_name),
                               str_sql(media_info.title),
                               media_info.category,
                               str_sql(media_info.year),
                               media_info.get_season_string(),
                               dest,
                               timestr))


# 查询识别转移记录
def get_transfer_history(search, page, rownum):
    if page == 1:
        begin_pos = 0
    else:
        begin_pos = (page - 1) * rownum

    if search:
        search = f"%{search}%"
        count_sql = "SELECT COUNT(1) FROM TRANSFER_HISTORY WHERE FILE_NAME LIKE ? OR TITLE LIKE ?"
        sql = "SELECT SOURCE, MODE, TYPE, FILE_NAME, TITLE, CATEGORY, YEAR, SE, DEST, DATE, ID" \
              " FROM TRANSFER_HISTORY" \
              " WHERE FILE_NAME LIKE ? OR TITLE LIKE ? ORDER BY DATE DESC LIMIT ? OFFSET ?"
        return select_by_sql(count_sql, (search, search)), select_by_sql(sql, (search, search, rownum, begin_pos))
    else:
        count_sql = "SELECT COUNT(1) FROM TRANSFER_HISTORY"
        sql = "SELECT SOURCE, MODE, TYPE, FILE_NAME, TITLE, CATEGORY, YEAR, SE, DEST, DATE, ID" \
              " FROM TRANSFER_HISTORY" \
              " ORDER BY DATE DESC LIMIT ? OFFSET ?"
    return select_by_sql(count_sql), select_by_sql(sql, (rownum, begin_pos))


# 根据logid查询PATH
def get_transfer_path_by_id(logid):
    sql = "SELECT FILE_PATH, FILE_NAME, DEST, TITLE, CATEGORY, YEAR, SE, TYPE FROM TRANSFER_HISTORY WHERE ID = ?"
    return select_by_sql(sql, (logid,))


# 根据logid删除记录
def delete_transfer_log_by_id(logid):
    sql = "DELETE FROM TRANSFER_HISTORY WHERE ID = ?"
    return update_by_sql(sql, (logid,))


# 查询未识别的记录列表
def get_transfer_unknown_paths():
    sql = "SELECT ID, PATH, DEST FROM TRANSFER_UNKNOWN WHERE STATE = 'N'"
    return select_by_sql(sql)


# 更新未识别记录为识别
def update_transfer_unknown_state(path):
    if not path:
        return False
    path = os.path.normpath(path)
    sql = "UPDATE TRANSFER_UNKNOWN SET STATE = 'Y' WHERE PATH = ?"
    return update_by_sql(sql, (str_sql(path),))


# 删除未识别记录
def delete_transfer_unknown(tid):
    if not tid:
        return False
    sql = "DELETE FROM TRANSFER_UNKNOWN WHERE ID = ?"
    return update_by_sql(sql, (tid,))


# 查询未识别记录
def get_unknown_path_by_id(tid):
    if not tid:
        return False
    sql = "SELECT PATH,DEST FROM TRANSFER_UNKNOWN WHERE ID = ?"
    return select_by_sql(sql, (tid,))


# 查询未识别记录是否存在
def is_transfer_unknown_exists(path):
    if not path:
        return False
    path = os.path.normpath(path)
    sql = "SELECT COUNT(1) FROM TRANSFER_UNKNOWN WHERE PATH = ?"
    ret = select_by_sql(sql, (str_sql(path),))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 插入未识别记录
def insert_transfer_unknown(path, dest):
    if not path:
        return False
    if is_transfer_unknown_exists(path):
        return False
    else:
        path = os.path.normpath(path)
        if dest:
            dest = os.path.normpath(dest)
        else:
            dest = ""
        sql = "INSERT INTO TRANSFER_UNKNOWN(PATH, DEST, STATE) VALUES (?, ?, ?)"
        return update_by_sql(sql, (str_sql(path), str_sql(dest), 'N'))


# 查询是否为黑名单
def is_transfer_in_blacklist(path):
    if not path:
        return False
    path = os.path.normpath(path)
    sql = "SELECT COUNT(1) FROM TRANSFER_BLACKLIST WHERE PATH = ?"
    ret = select_by_sql(sql, (str_sql(path),))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 查询是否为黑名单
def is_transfer_notin_blacklist(path):
    return not is_transfer_in_blacklist(path)


# 插入黑名单记录
def insert_transfer_blacklist(path):
    if not path:
        return False
    if is_transfer_in_blacklist(path):
        return False
    else:
        path = os.path.normpath(path)
        sql = "INSERT INTO TRANSFER_BLACKLIST(PATH) VALUES (?)"
        return update_by_sql(sql, (str_sql(path),))


# 清空黑名单记录
def truncate_transfer_blacklist():
    sql = "DELETE FROM TRANSFER_BLACKLIST"
    return update_by_sql(sql)


# 查询所有站点信息
def get_config_site():
    return select_by_sql(
        "SELECT ID,NAME,PRI,RSSURL,SIGNURL,COOKIE,INCLUDE,EXCLUDE,SIZE,NOTE"
        " FROM CONFIG_SITE"
        " ORDER BY CAST(PRI AS DECIMAL) ASC")


# 查询1个站点信息
def get_site_by_id(tid):
    return select_by_sql(
        "SELECT ID,NAME,PRI,RSSURL,SIGNURL,COOKIE,INCLUDE,EXCLUDE,SIZE,NOTE FROM CONFIG_SITE WHERE ID = ?", (tid,))


# 插入站点信息
def insert_config_site(name, site_pri, rssurl, signurl, cookie, note):
    if not name:
        return
    sql = "INSERT INTO CONFIG_SITE(NAME,PRI,RSSURL,SIGNURL,COOKIE,NOTE) VALUES " \
          "(?, ?, ?, ?, ?, ?)"
    return update_by_sql(sql, (str_sql(name),
                               str_sql(site_pri),
                               str_sql(rssurl),
                               str_sql(signurl),
                               str_sql(cookie),
                               str_sql(note)))


# 删除站点信息
def delete_config_site(tid):
    if not tid:
        return False
    return update_by_sql("DELETE FROM CONFIG_SITE WHERE ID = ?", (tid,))


# 更新站点信息
def update_config_site(tid, name, site_pri, rssurl, signurl, cookie, note):
    if not tid:
        return
    sql = "UPDATE CONFIG_SITE SET NAME=?,PRI=?,RSSURL=?,SIGNURL=?,COOKIE=?,NOTE=? WHERE ID=?"
    return update_by_sql(sql, (str_sql(name),
                               str_sql(site_pri),
                               str_sql(rssurl),
                               str_sql(signurl),
                               str_sql(cookie),
                               str_sql(note),
                               tid))


# 查询过滤规则组
def get_config_filter_group():
    return select_by_sql("SELECT ID,GROUP_NAME,IS_DEFAULT,NOTE FROM CONFIG_FILTER_GROUP")


# 查询过滤规则
def get_config_filter_rule(groupid=None):
    if not groupid:
        return select_by_sql("SELECT "
                             "ID,GROUP_ID,ROLE_NAME,PRIORITY,INCLUDE,EXCLUDE,SIZE_LIMIT,NOTE "
                             "FROM CONFIG_FILTER_RULES "
                             "ORDER BY GROUP_ID, CAST(PRIORITY AS DECIMAL) ASC")
    else:
        return select_by_sql("SELECT "
                             "ID,GROUP_ID,ROLE_NAME,PRIORITY,INCLUDE,EXCLUDE,SIZE_LIMIT,NOTE "
                             "FROM CONFIG_FILTER_RULES "
                             "WHERE GROUP_ID = ? "
                             "ORDER BY CAST(PRIORITY AS DECIMAL) ASC", (groupid,))


# 查询订阅电影信息
def get_rss_movies(state=None, rssid=None):
    if rssid:
        sql = "SELECT NAME,YEAR,TMDBID,IMAGE,DESC,STATE,ID FROM RSS_MOVIES WHERE ID = ?"
        return select_by_sql(sql, (rssid,))
    else:
        if not state:
            sql = "SELECT NAME,YEAR,TMDBID,IMAGE,DESC,STATE,ID FROM RSS_MOVIES"
            return select_by_sql(sql)
        else:
            sql = "SELECT NAME,YEAR,TMDBID,IMAGE,DESC,STATE,ID FROM RSS_MOVIES WHERE STATE = ?"
            return select_by_sql(sql, (state,))


# 获取订阅电影ID
def get_rss_movie_id(title, year):
    if not title:
        return ""
    sql = "SELECT ID FROM RSS_MOVIES WHERE NAME=? AND YEAR = ?"
    ret = select_by_sql(sql, (str_sql(title), str_sql(year)))
    if ret:
        return ret[0][0]
    return ""


# 获取订阅电影站点
def get_rss_movie_sites(rssid):
    if not rssid:
        return ""
    sql = "SELECT DESC FROM RSS_MOVIES WHERE ID = ?"
    ret = select_by_sql(sql, (rssid,))
    if ret:
        return ret[0][0]
    return ""


# 更新订阅电影的TMDBID
def update_rss_movie_tmdb(rid, tmdbid, title, year, image):
    if not tmdbid:
        return False
    sql = "UPDATE RSS_MOVIES SET TMDBID = ?, NAME = ?, YEAR = ?, IMAGE = ? WHERE ID = ?"
    return update_by_sql(sql, (tmdbid, str_sql(title), str_sql(year), str_sql(image), rid))


# 判断RSS电影是否存在
def is_exists_rss_movie(title, year):
    if not title:
        return False
    sql = "SELECT COUNT(1) FROM RSS_MOVIES WHERE NAME=? AND YEAR = ?"
    ret = select_by_sql(sql, (str_sql(title), str_sql(year)))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 新增RSS电影
def insert_rss_movie(media_info: MetaBase,
                     state='D',
                     sites: list = None,
                     search_sites: list = None,
                     over_edition=False,
                     rss_restype=None,
                     rss_pix=None,
                     rss_rule=None):
    if not media_info:
        return False
    if not media_info.title:
        return False
    if is_exists_rss_movie(media_info.title, media_info.year):
        return True
    sql = "INSERT INTO RSS_MOVIES(NAME,YEAR,TMDBID,IMAGE,DESC,STATE) VALUES (?, ?, ?, ?, ?, ?)"
    desc = "#".join(["|".join(sites or []),
                     "|".join(search_sites or []),
                     "Y" if over_edition else "N",
                     "%s@%s@%s" % (str_sql(rss_restype),
                                   str_sql(rss_pix),
                                   str_sql(rss_rule))])
    return update_by_sql(sql, (str_sql(media_info.title),
                               str_sql(media_info.year),
                               str_sql(media_info.tmdb_id),
                               str_sql(media_info.get_message_image()),
                               desc,
                               state))


# 删除RSS电影
def delete_rss_movie(title=None, year=None, rssid=None):
    if not title and not rssid:
        return False
    if rssid:
        sql = "DELETE FROM RSS_MOVIES WHERE ID = ?"
        return update_by_sql(sql, (rssid,))
    else:
        sql = "DELETE FROM RSS_MOVIES WHERE NAME = ? AND YEAR = ?"
        return update_by_sql(sql, (str_sql(title), str_sql(year)))


# 更新电影订阅状态
def update_rss_movie_state(title=None, year=None, rssid=None, state='R'):
    if not title and not rssid:
        return False
    if rssid:
        sql = "UPDATE RSS_MOVIES SET STATE = ? WHERE ID = ?"
        return update_by_sql(sql, (state, rssid))
    else:
        sql = "UPDATE RSS_MOVIES SET STATE = ? WHERE NAME = ? AND YEAR = ?"
        return update_by_sql(sql, (state, str_sql(title), str_sql(year)))


# 查询订阅电视剧信息
def get_rss_tvs(state=None, rssid=None):
    if rssid:
        sql = "SELECT NAME,YEAR,SEASON,TMDBID,IMAGE,DESC,TOTAL,LACK,STATE" \
              ",((CAST(TOTAL AS FLOAT)-CAST(LACK AS FLOAT))/CAST(TOTAL AS FLOAT))*100,ID" \
              " FROM RSS_TVS" \
              " WHERE ID = ?"
        return select_by_sql(sql, (rssid,))
    else:
        if not state:
            sql = "SELECT NAME,YEAR,SEASON,TMDBID,IMAGE,DESC,TOTAL,LACK,STATE" \
                  ",((CAST(TOTAL AS FLOAT)-CAST(LACK AS FLOAT))/CAST(TOTAL AS FLOAT))*100,ID" \
                  " FROM RSS_TVS"
            return select_by_sql(sql)
        else:
            sql = "SELECT NAME,YEAR,SEASON,TMDBID,IMAGE,DESC,TOTAL,LACK,STATE" \
                  ",((CAST(TOTAL AS FLOAT)-CAST(LACK AS FLOAT))/CAST(TOTAL AS FLOAT))*100,ID" \
                  " FROM RSS_TVS WHERE STATE = ?"
            return select_by_sql(sql, (state,))


# 获取订阅电影ID
def get_rss_tv_id(title, year, season=None):
    if not title:
        return ""
    if season:
        sql = "SELECT ID FROM RSS_TVS WHERE NAME = ? AND YEAR = ? AND SEASON = ?"
        ret = select_by_sql(sql, (str_sql(title), str_sql(year), season))
    else:
        sql = "SELECT ID FROM RSS_TVS WHERE NAME = ? AND YEAR = ?"
        ret = select_by_sql(sql, (str_sql(title), str_sql(year)))
    if ret:
        return ret[0][0]
    return ""


# 获取订阅电视剧站点
def get_rss_tv_sites(rssid):
    if not rssid:
        return ""
    sql = "SELECT DESC FROM RSS_TVS WHERE ID = ?"
    ret = select_by_sql(sql, (rssid,))
    if ret:
        return ret[0][0]
    return ""


# 更新订阅电影的TMDBID
def update_rss_tv_tmdb(rid, tmdbid, title, year, total, image):
    if not tmdbid:
        return False
    sql = "UPDATE RSS_TVS SET TMDBID = ?, NAME = ?, YEAR = ?, TOTAL = ?, IMAGE = ? WHERE ID = ?"
    return update_by_sql(sql, (tmdbid, str_sql(title), year, total, str_sql(image), rid))


# 判断RSS电视剧是否存在
def is_exists_rss_tv(title, year, season=None):
    if not title:
        return False
    if season:
        sql = "SELECT COUNT(1) FROM RSS_TVS WHERE NAME = ? AND YEAR = ? AND SEASON = ?"
        ret = select_by_sql(sql, (str_sql(title), str_sql(year), season))
    else:
        sql = "SELECT COUNT(1) FROM RSS_TVS WHERE NAME = ? AND YEAR = ?"
        ret = select_by_sql(sql, (str_sql(title), str_sql(year)))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 新增RSS电视剧
def insert_rss_tv(media_info: MetaBase, total, lack=0, state="D",
                  sites: list = None,
                  search_sites: list = None,
                  over_edition=False,
                  rss_restype=None,
                  rss_pix=None,
                  rss_rule=None,
                  match=False
                  ):
    if not media_info:
        return False
    if not media_info.title:
        return False
    if match and not media_info.begin_season:
        season_str = ""
    else:
        season_str = media_info.get_season_string()
    if is_exists_rss_tv(media_info.title, media_info.year, season_str):
        return True
    # 插入订阅数据
    sql = "INSERT INTO RSS_TVS(NAME,YEAR,SEASON,TMDBID,IMAGE,DESC,TOTAL,LACK,STATE) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    desc = "#".join(["|".join(sites or []),
                     "|".join(search_sites or []),
                     "Y" if over_edition else "N",
                     "@".join([str_sql(rss_restype),
                               str_sql(rss_pix),
                               str_sql(rss_rule)])])
    return update_by_sql(sql, (str_sql(media_info.title),
                               str_sql(media_info.year),
                               season_str,
                               str_sql(media_info.tmdb_id),
                               str_sql(media_info.get_message_image()),
                               desc,
                               total,
                               lack,
                               state))


# 更新电视剧缺失的集数
def update_rss_tv_lack(title=None, year=None, season=None, rssid=None, lack_episodes: list = None):
    if not title and not rssid:
        return False
    if not lack_episodes:
        lack = 0
    else:
        lack = len(lack_episodes)
    if rssid:
        update_rss_tv_episodes(rssid, lack_episodes)
        sql = "UPDATE RSS_TVS SET LACK=? WHERE ID = ?"
        return update_by_sql(sql, (lack, rssid))
    else:
        sql = "UPDATE RSS_TVS SET LACK=? WHERE NAME = ? AND YEAR = ? AND SEASON = ?"
        return update_by_sql(sql, (lack, str_sql(title), str_sql(year), season))


# 删除RSS电视剧
def delete_rss_tv(title=None, year=None, season=None, rssid=None):
    if not title and not rssid:
        return False
    if rssid:
        delete_rss_tv_episodes(rssid)
        sql = "DELETE FROM RSS_TVS WHERE ID = ?"
        return update_by_sql(sql, (rssid,))
    else:
        sql = "DELETE FROM RSS_TVS WHERE NAME = ? AND YEAR = ? AND SEASON = ?"
        return update_by_sql(sql, (str_sql(title), str_sql(year), season))


# 判断RSS电视剧是否存在
def is_exists_rss_tv_episodes(rid):
    if not rid:
        return False
    sql = "SELECT COUNT(1) FROM RSS_TV_EPISODES WHERE RSSID = ?"
    ret = select_by_sql(sql, (rid,))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 插入或更新电视剧订阅缺失剧集
def update_rss_tv_episodes(rid, episodes):
    if not rid:
        return
    if not episodes:
        episodes = []
    else:
        episodes = [str(epi) for epi in episodes]
    if is_exists_rss_tv_episodes(rid):
        sql = "UPDATE RSS_TV_EPISODES SET EPISODES = ? WHERE RSSID = ?"
        ret = update_by_sql(sql, (",".join(episodes), rid))
    else:
        sql = "INSERT INTO RSS_TV_EPISODES(RSSID, EPISODES) VALUES(?, ?)"
        ret = update_by_sql(sql, (rid, ",".join(episodes)))
    return ret


# 查询电视剧订阅缺失剧集
def get_rss_tv_episodes(rid):
    if not rid:
        return []
    sql = "SELECT EPISODES FROM RSS_TV_EPISODES WHERE RSSID = ?"
    ret = select_by_sql(sql, (rid,))
    if ret:
        return [int(epi) for epi in str(ret[0][0]).split(',')]
    else:
        return None


# 删除电视剧订阅缺失剧集
def delete_rss_tv_episodes(rid):
    if not rid:
        return []
    sql = "DELETE FROM RSS_TV_EPISODES WHERE RSSID = ?"
    return update_by_sql(sql, (rid,))


# 更新电视剧订阅状态
def update_rss_tv_state(title=None, year=None, season=None, rssid=None, state='R'):
    if not title and not rssid:
        return False
    if rssid:
        sql = "UPDATE RSS_TVS SET STATE = ? WHERE ID = ?"
        return update_by_sql(sql, (state, rssid))
    else:
        sql = "UPDATE RSS_TVS SET STATE = ? WHERE NAME = ? AND YEAR = ? AND SEASON = ?"
        return update_by_sql(sql, (state, str_sql(title), str_sql(year), season))


# 查询是否存在同步历史记录
def is_sync_in_history(path, dest):
    if not path:
        return False
    path = os.path.normpath(path)
    dest = os.path.normpath(dest)
    sql = "SELECT COUNT(1) FROM SYNC_HISTORY WHERE PATH = ? AND DEST = ?"
    ret = select_by_sql(sql, (str_sql(path), str_sql(dest)))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 插入黑名单记录
def insert_sync_history(path, src, dest):
    if not path or not dest:
        return False
    if is_sync_in_history(path, dest):
        return False
    else:
        path = os.path.normpath(path)
        src = os.path.normpath(src)
        dest = os.path.normpath(dest)
        sql = "INSERT INTO SYNC_HISTORY(PATH, SRC, DEST) VALUES (?, ?, ?)"
        return update_by_sql(sql, (str_sql(path), str_sql(src), str_sql(dest)))


# 查询用户列表
def get_users():
    sql = "SELECT ID,NAME,PASSWORD,PRIS FROM CONFIG_USERS"
    return select_by_sql(sql)


# 判断用户是否存在
def is_user_exists(name):
    if not name:
        return False
    sql = "SELECT COUNT(1) FROM CONFIG_USERS WHERE NAME = ?"
    ret = select_by_sql(sql, (name,))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 新增用户
def insert_user(name, password, pris):
    if not name or not password:
        return False
    if is_user_exists(name):
        return False
    else:
        sql = "INSERT INTO CONFIG_USERS(NAME,PASSWORD,PRIS) VALUES (?, ?, ?)"
        return update_by_sql(sql, (str_sql(name), str_sql(password), str_sql(pris)))


# 删除用户
def delete_user(name):
    return update_by_sql("DELETE FROM CONFIG_USERS WHERE NAME = ?", (str_sql(name),))


# 查询历史记录统计
def get_transfer_statistics(days=30):
    begin_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    sql = "SELECT TYPE,SUBSTR(DATE, 1, 10),COUNT(1)" \
          " FROM TRANSFER_HISTORY" \
          " WHERE DATE > ? GROUP BY TYPE,SUBSTR(DATE, 1, 10)"
    return select_by_sql(sql, (begin_date,))


# 更新站点用户粒度数据
def update_site_user_statistics(site_user_infos: list):
    if not site_user_infos:
        return
    update_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    sql = "INSERT OR REPLACE INTO SITE_USER_INFO_STATISTICS(SITE, USERNAME, USER_LEVEL," \
          " JOIN_AT, UPDATE_AT," \
          " UPLOAD, DOWNLOAD, RATIO," \
          " SEEDING, LEECHING, SEEDING_SIZE," \
          " BONUS," \
          " URL, FAVICON) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

    data_list = []

    for site_user_info in site_user_infos:
        site = site_user_info.site_name
        username = site_user_info.username
        user_level = site_user_info.user_level
        join_at = site_user_info.join_at
        upload = site_user_info.upload
        download = site_user_info.download
        ratio = site_user_info.ratio
        seeding = site_user_info.seeding
        seeding_size = site_user_info.seeding_size
        leeching = site_user_info.leeching
        bonus = site_user_info.bonus
        url = site_user_info.site_url
        favicon = site_user_info.site_favicon

        data_list.append((
            str_sql(site), username, user_level, join_at, update_at, upload, download, ratio, seeding, leeching,
            seeding_size, bonus, url, favicon))
    return update_by_sql_batch(sql, data_list)


# 更新站点做种数据
def update_site_seed_info(site_user_infos: list):
    if not site_user_infos:
        return
    update_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    sql = "INSERT OR REPLACE INTO SITE_USER_SEEDING_INFO(SITE, UPDATE_AT," \
          " SEEDING_INFO," \
          " URL) VALUES (?, ?, ?, ?)"

    data_list = []
    for site_user_info in site_user_infos:
        data_list.append((str_sql(site_user_info.site_name), update_at, site_user_info.seeding_info,
                          site_user_info.site_url))

    return update_by_sql_batch(sql, data_list)


# 判断站点用户数据是否存在
def is_site_user_statistics_exists(url):
    if not url:
        return False
    sql = "SELECT COUNT(1) FROM SITE_USER_INFO_STATISTICS WHERE URL = ? "
    ret = select_by_sql(sql, (url,))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 查询站点数据历史
def get_site_user_statistics(num=100, strict_urls=None):
    if strict_urls is None:
        strict_urls = []

    sql = "SELECT SITE, USERNAME, USER_LEVEL," \
          " JOIN_AT, UPDATE_AT," \
          " UPLOAD, DOWNLOAD, RATIO," \
          " SEEDING, LEECHING, SEEDING_SIZE," \
          " BONUS, URL, FAVICON" \
          " FROM SITE_USER_INFO_STATISTICS LIMIT ?"
    if strict_urls:
        sql = "SELECT SITE, USERNAME, USER_LEVEL," \
              " JOIN_AT, UPDATE_AT," \
              " UPLOAD, DOWNLOAD, RATIO," \
              " SEEDING, LEECHING, SEEDING_SIZE," \
              " BONUS, URL, FAVICON" \
              " FROM SITE_USER_INFO_STATISTICS WHERE URL in {} LIMIT ?".format(tuple(strict_urls + ["__DUMMY__"]))

    return select_by_sql(sql, (num,))


# 判断站点历史数据是否存在
def is_site_statistics_history_exists(url, date):
    if not url or not date:
        return False
    sql = "SELECT COUNT(1) FROM SITE_STATISTICS_HISTORY WHERE URL = ? AND DATE = ?"
    ret = select_by_sql(sql, (url, date))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 插入站点数据
def insert_site_statistics_history(site_user_infos: list):
    if not site_user_infos:
        return

    date_now = time.strftime('%Y-%m-%d', time.localtime(time.time()))
    sql = "INSERT OR REPLACE INTO SITE_STATISTICS_HISTORY(SITE, USER_LEVEL, DATE, UPLOAD, DOWNLOAD, RATIO," \
          " SEEDING, LEECHING, SEEDING_SIZE," \
          " BONUS," \
          " URL) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

    data_list = []
    for site_user_info in site_user_infos:
        site = site_user_info.site_name
        upload = site_user_info.upload
        user_level = site_user_info.user_level
        download = site_user_info.download
        ratio = site_user_info.ratio
        seeding = site_user_info.seeding
        seeding_size = site_user_info.seeding_size
        leeching = site_user_info.leeching
        bonus = site_user_info.bonus
        url = site_user_info.site_url

        data_list.append((str_sql(site), user_level, date_now, upload, download, ratio, seeding, leeching,
                          seeding_size, bonus, url))

    return update_by_sql_batch(sql, data_list)


# 查询站点数据历史
def get_site_statistics_history(site, days=30):
    sql = "SELECT DATE, UPLOAD, DOWNLOAD, BONUS, SEEDING, SEEDING_SIZE " \
          "FROM SITE_STATISTICS_HISTORY WHERE SITE = ? ORDER BY DATE ASC LIMIT ?"
    return select_by_sql(sql, (site, days,))


# 查询站点做种信息
def get_site_seeding_info(site):
    sql = "SELECT SEEDING_INFO " \
          "FROM SITE_USER_SEEDING_INFO WHERE SITE = ? LIMIT 1"
    return select_by_sql(sql, (site,))


# 查询近期上传下载量
def get_site_statistics_recent_sites(days=7, strict_urls=None):
    # 查询最大最小日期
    if strict_urls is None:
        strict_urls = []

    b_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    date_sql = "SELECT MAX(DATE), MIN(DATE) FROM SITE_STATISTICS_HISTORY WHERE DATE > ? "
    date_ret = select_by_sql(date_sql, (b_date,))
    if date_ret:
        total_upload = 0
        total_download = 0
        ret_sites = []
        ret_site_uploads = []
        ret_site_downloads = []
        min_date = date_ret[0][1]
        # 查询开始值
        sql = """SELECT SITE, MIN(UPLOAD), MIN(DOWNLOAD), MAX(UPLOAD), MAX(DOWNLOAD)
                 FROM (SELECT SITE, DATE, SUM(UPLOAD) as UPLOAD, SUM(DOWNLOAD) as DOWNLOAD FROM SITE_STATISTICS_HISTORY WHERE DATE >= ? GROUP BY SITE, DATE) X 
                 GROUP BY SITE"""
        if strict_urls:
            sql = """
                 SELECT SITE, MIN(UPLOAD), MIN(DOWNLOAD), MAX(UPLOAD), MAX(DOWNLOAD)
                 FROM (SELECT SITE, DATE, SUM(UPLOAD) as UPLOAD, SUM(DOWNLOAD) as DOWNLOAD FROM SITE_STATISTICS_HISTORY WHERE DATE >= ? AND URL in {} GROUP BY SITE, DATE) X 
                 GROUP BY SITE""".format(tuple(strict_urls + ["__DUMMY__"]))
        for ret_b in select_by_sql(sql, (min_date,)):
            # 如果最小值都是0，可能时由于近几日没有更新数据，或者cookie过期，正常有数据的话，第二天能正常
            ret_b = list(ret_b)
            if ret_b[1] == 0 and ret_b[2] == 0:
                ret_b[1] = ret_b[3]
                ret_b[2] = ret_b[4]
            ret_sites.append(ret_b[0])
            if int(ret_b[1]) < int(ret_b[3]):
                total_upload += int(ret_b[3]) - int(ret_b[1])
                ret_site_uploads.append(int(ret_b[3]) - int(ret_b[1]))
            else:
                ret_site_uploads.append(0)
            if int(ret_b[2]) < int(ret_b[4]):
                total_download += int(ret_b[4]) - int(ret_b[2])
                ret_site_downloads.append(int(ret_b[4]) - int(ret_b[2]))
            else:
                ret_site_downloads.append(0)
        return total_upload, total_download, ret_sites, ret_site_uploads, ret_site_downloads
    else:
        return 0, 0, [], [], []


# 查询下载历史是否存在
def is_exists_download_history(title, year, mtype=None):
    if not title:
        return False
    if mtype:
        sql = "SELECT COUNT(1) FROM DOWNLOAD_HISTORY WHERE TITLE = ? AND YEAR = ? AND TYPE = ?"
        ret = select_by_sql(sql, (str_sql(title), str_sql(year), mtype))
    else:
        sql = "SELECT COUNT(1) FROM DOWNLOAD_HISTORY WHERE TITLE = ? AND YEAR = ?"
        ret = select_by_sql(sql, (str_sql(title), str_sql(year)))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 新增下载历史
def insert_download_history(media_info: MetaBase):
    if not media_info:
        return False
    if not media_info.title or not media_info.year:
        return False
    if is_exists_download_history(media_info.title, media_info.year, media_info.type.value):
        sql = "UPDATE DOWNLOAD_HISTORY SET TORRENT = ?, ENCLOSURE = ?, DESC = ?, DATE = ?, SITE = ? WHERE TITLE = ? AND YEAR = ? AND TYPE = ?"
        return update_by_sql(sql, (str_sql(media_info.org_string),
                                   str_sql(media_info.enclosure),
                                   str_sql(media_info.description),
                                   time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                                   str_sql(media_info.site),
                                   str_sql(media_info.title),
                                   str_sql(media_info.year),
                                   media_info.type.value,))
    else:
        sql = "INSERT INTO DOWNLOAD_HISTORY(TITLE,YEAR,TYPE,TMDBID,VOTE,POSTER,OVERVIEW,TORRENT,ENCLOSURE,DESC,DATE,SITE) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        return update_by_sql(sql, (str_sql(media_info.title),
                                   str_sql(media_info.year),
                                   media_info.type.value,
                                   media_info.tmdb_id,
                                   media_info.vote_average,
                                   media_info.get_poster_image(),
                                   str_sql(media_info.overview),
                                   str_sql(media_info.org_string),
                                   str_sql(media_info.enclosure),
                                   str_sql(media_info.description),
                                   time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                                   str_sql(media_info.site),))


# 查询下载历史
def get_download_history(date=None, hid=None, num=30, page=1):
    if hid:
        sql = "SELECT ID,TITLE,YEAR,TYPE,TMDBID,VOTE,POSTER,OVERVIEW,TORRENT,ENCLOSURE,DESC,DATE,SITE FROM DOWNLOAD_HISTORY WHERE ID = ?"
        return select_by_sql(sql, (hid,))
    elif date:
        sql = "SELECT ID,TITLE,YEAR,TYPE,TMDBID,VOTE,POSTER,OVERVIEW,TORRENT,ENCLOSURE,DESC,DATE,SITE FROM DOWNLOAD_HISTORY WHERE DATE > ? ORDER BY DATE DESC"
        return select_by_sql(sql, (date,))
    else:
        offset = (int(page) - 1) * int(num)
        sql = "SELECT ID,TITLE,YEAR,TYPE,TMDBID,VOTE,POSTER,OVERVIEW,TORRENT,ENCLOSURE,DESC,DATE,SITE FROM DOWNLOAD_HISTORY ORDER BY DATE DESC LIMIT ? OFFSET ?"
        return select_by_sql(sql, (num, offset))


# 根据标题和年份检查是否下载过
def is_media_downloaded(title, year):
    if is_exists_download_history(title, year):
        return True
    sql = "SELECT COUNT(1) FROM TRANSFER_HISTORY WHERE TITLE = ? AND YEAR = ?"
    ret = select_by_sql(sql, (str_sql(title), str_sql(year)))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 新增刷流任务
def insert_brushtask(brush_id, item):
    if not brush_id:
        sql = '''
            INSERT INTO SITE_BRUSH_TASK(
                NAME,
                SITE,
                FREELEECH,
                RSS_RULE,
                REMOVE_RULE,
                SEED_SIZE,
                INTEVAL,
                DOWNLOADER,
                TRANSFER,
                DOWNLOAD_COUNT,
                REMOVE_COUNT,
                DOWNLOAD_SIZE,
                UPLOAD_SIZE,
                STATE,
                LST_MOD_DATE
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        '''
        return update_by_sql(sql, (item.get('name'),
                                   item.get('site'),
                                   item.get('free'),
                                   str(item.get('rss_rule')),
                                   str(item.get('remove_rule')),
                                   item.get('seed_size'),
                                   item.get('interval'),
                                   item.get('downloader'),
                                   item.get('transfer'),
                                   0,
                                   0,
                                   0,
                                   0,
                                   item.get('state'),
                                   time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))
    else:
        sql = '''
            UPDATE SITE_BRUSH_TASK SET
                NAME = ?,
                SITE = ?,
                FREELEECH = ?,
                RSS_RULE = ?,
                REMOVE_RULE = ?,
                SEED_SIZE = ?,
                INTEVAL = ?,
                DOWNLOADER = ?,
                TRANSFER = ?,
                STATE = ?,
                LST_MOD_DATE = ?
            WHERE ID = ?
        '''
        return update_by_sql(sql, (item.get('name'),
                                   item.get('site'),
                                   item.get('free'),
                                   str(item.get('rss_rule')),
                                   str(item.get('remove_rule')),
                                   item.get('seed_size'),
                                   item.get('interval'),
                                   item.get('downloader'),
                                   item.get('transfer'),
                                   item.get('state'),
                                   time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                                   brush_id))


# 删除刷流任务
def delete_brushtask(brush_id):
    sql = "DELETE FROM SITE_BRUSH_TASK WHERE ID = ?"
    update_by_sql(sql, (brush_id,))
    sql = "DELETE FROM SITE_BRUSH_TORRENTS WHERE TASK_ID = ?"
    update_by_sql(sql, (brush_id,))


# 查询刷流任务
def get_brushtasks(brush_id=None):
    if brush_id:
        sql = "SELECT T.ID,T.NAME,T.SITE,C.NAME,T.INTEVAL,T.STATE,T.DOWNLOADER,T.TRANSFER," \
              "T.FREELEECH,T.RSS_RULE,T.REMOVE_RULE,T.SEED_SIZE," \
              "T.DOWNLOAD_COUNT,T.REMOVE_COUNT,T.DOWNLOAD_SIZE,T.UPLOAD_SIZE,T.LST_MOD_DATE,C.RSSURL,C.COOKIE,D.NAME " \
              "FROM SITE_BRUSH_TASK T " \
              "LEFT JOIN CONFIG_SITE C ON C.ID = T.SITE " \
              "LEFT JOIN SITE_BRUSH_DOWNLOADERS D ON D.ID = T.DOWNLOADER " \
              "WHERE T.ID = ?"
        return select_by_sql(sql, (brush_id,))
    else:
        sql = "SELECT T.ID,T.NAME,T.SITE,C.NAME,T.INTEVAL,T.STATE,T.DOWNLOADER,T.TRANSFER," \
              "T.FREELEECH,T.RSS_RULE,T.REMOVE_RULE,T.SEED_SIZE," \
              "T.DOWNLOAD_COUNT,T.REMOVE_COUNT,T.DOWNLOAD_SIZE,T.UPLOAD_SIZE,T.LST_MOD_DATE,C.RSSURL,C.COOKIE,D.NAME " \
              "FROM SITE_BRUSH_TASK T " \
              "LEFT JOIN CONFIG_SITE C ON C.ID = T.SITE " \
              "LEFT JOIN SITE_BRUSH_DOWNLOADERS D ON D.ID = T.DOWNLOADER "
        return select_by_sql(sql)


# 查询刷流任务总体积
def get_brushtask_totalsize(brush_id):
    if not brush_id:
        return 0
    sql = "SELECT SUM(CAST(S.TORRENT_SIZE AS DECIMAL)) FROM SITE_BRUSH_TORRENTS S WHERE S.TASK_ID = ? AND S.DOWNLOAD_ID <> '0'"
    ret = select_by_sql(sql, (brush_id,))
    if ret and ret[0][0]:
        return int(ret[0][0])
    else:
        return 0


# 增加刷流下载数
def add_brushtask_download_count(brush_id):
    if not brush_id:
        return
    sql = "UPDATE SITE_BRUSH_TASK SET DOWNLOAD_COUNT = DOWNLOAD_COUNT + 1, LST_MOD_DATE = ? WHERE ID = ?"
    return update_by_sql(sql, (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())), brush_id))


# 获取已删除种子的上传量
def get_brushtask_remove_size(brush_id):
    if not brush_id:
        return 0
    sql = "SELECT S.TORRENT_SIZE FROM SITE_BRUSH_TORRENTS S WHERE S.TASK_ID = ? AND S.DOWNLOAD_ID = '0'"
    return select_by_sql(sql, (brush_id,))


# 更新上传下载量和删除种子数
def add_brushtask_upload_count(brush_id, upload_size, download_size, remove_count):
    if not brush_id:
        return
    delete_upsize = 0
    delete_dlsize = 0
    remove_sizes = get_brushtask_remove_size(brush_id)
    for remove_size in remove_sizes:
        if not remove_size[0]:
            continue
        if str(remove_size[0]).find(",") != -1:
            sizes = str(remove_size[0]).split(",")
            delete_upsize += int(sizes[0] or 0)
            if len(sizes) > 1:
                delete_dlsize += int(sizes[1] or 0)
        else:
            delete_upsize += int(remove_size[0])
    sql = "UPDATE SITE_BRUSH_TASK SET REMOVE_COUNT = REMOVE_COUNT + ?, UPLOAD_SIZE = ?, DOWNLOAD_SIZE = ? WHERE ID = ?"
    return update_by_sql(sql,
                         (remove_count, int(upload_size) + delete_upsize, int(download_size) + delete_dlsize, brush_id))


# 增加刷流下载的种子信息
def insert_brushtask_torrent(brush_id, title, enclosure, downloader, download_id, size):
    if not brush_id:
        return
    sql = '''
        INSERT INTO SITE_BRUSH_TORRENTS(
            TASK_ID,
            TORRENT_NAME,
            TORRENT_SIZE,
            ENCLOSURE,
            DOWNLOADER,
            DOWNLOAD_ID,
            LST_MOD_DATE
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?
        )
    '''
    if is_brushtask_torrent_exists(brush_id, title, enclosure):
        return False
    return update_by_sql(sql, (brush_id,
                               title,
                               size,
                               enclosure,
                               downloader,
                               download_id,
                               time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))


# 查询刷流任务所有种子
def get_brushtask_torrents(brush_id):
    if not brush_id:
        return []
    sql = "SELECT ID,TASK_ID,TORRENT_NAME,TORRENT_SIZE,ENCLOSURE,DOWNLOADER,DOWNLOAD_ID,LST_MOD_DATE " \
          "FROM SITE_BRUSH_TORRENTS " \
          "WHERE TASK_ID = ? " \
          "AND DOWNLOAD_ID <> '0'"
    return select_by_sql(sql, (brush_id,))


# 查询刷流任务种子是否已存在
def is_brushtask_torrent_exists(brush_id, title, enclosure):
    if not brush_id:
        return False
    sql = "SELECT COUNT(1) FROM SITE_BRUSH_TORRENTS WHERE TASK_ID = ? AND TORRENT_NAME = ? AND ENCLOSURE = ?"
    ret = select_by_sql(sql, (brush_id, title, enclosure))
    if ret and ret[0][0] > 0:
        return True
    else:
        return False


# 更新刷流种子的状态
def update_brushtask_torrent_state(ids: list):
    if not ids:
        return
    sql = "UPDATE SITE_BRUSH_TORRENTS SET TORRENT_SIZE = ?, DOWNLOAD_ID = '0' WHERE TASK_ID = ? AND DOWNLOAD_ID = ?"
    return update_by_sql_batch(sql, ids)


# 查询自定义下载器
def get_user_downloaders(did=None):
    if did:
        sql = "SELECT ID,NAME,TYPE,HOST,PORT,USERNAME,PASSWORD,SAVE_DIR,NOTE FROM SITE_BRUSH_DOWNLOADERS WHERE ID = ?"
        return select_by_sql(sql, (did,))
    else:
        sql = "SELECT ID,NAME,TYPE,HOST,PORT,USERNAME,PASSWORD,SAVE_DIR,NOTE FROM SITE_BRUSH_DOWNLOADERS"
        return select_by_sql(sql)


# 新增自定义下载器
def insert_user_downloader(name, dtype, user_config, note):
    sql = "INSERT INTO SITE_BRUSH_DOWNLOADERS (NAME,TYPE,HOST,PORT,USERNAME,PASSWORD,SAVE_DIR,NOTE)" \
          "VALUES (?,?,?,?,?,?,?,?)"
    return update_by_sql(sql, (str_sql(name),
                               dtype,
                               str_sql(user_config.get("host")),
                               str_sql(user_config.get("port")),
                               str_sql(user_config.get("username")),
                               str_sql(user_config.get("password")),
                               str_sql(user_config.get("save_dir")),
                               str_sql(note)))


# 删除自定义下载器
def delete_user_downloader(did):
    sql = "DELETE FROM SITE_BRUSH_DOWNLOADERS WHERE ID = ?"
    return update_by_sql(sql, (did,))


# 新增规则组
def add_filter_group(name, default='N'):
    if default == 'Y':
        set_default_filtergroup(0)
    sql = "INSERT INTO CONFIG_FILTER_GROUP (GROUP_NAME, IS_DEFAULT) VALUES (?, ?)"
    update_by_sql(sql, (str_sql(name), default))
    return True


# 设置默认的规则组
def set_default_filtergroup(groupid):
    sql = "UPDATE CONFIG_FILTER_GROUP SET IS_DEFAULT = 'Y' WHERE ID = ?"
    update_by_sql(sql, (groupid,))
    sql = "UPDATE CONFIG_FILTER_GROUP SET IS_DEFAULT = 'N' WHERE ID <> ?"
    return update_by_sql(sql, (groupid,))


# 删除规则组
def delete_filtergroup(groupid):
    sql = "DELETE FROM CONFIG_FILTER_RULES WHERE GROUP_ID = ?"
    update_by_sql(sql, (groupid,))
    sql = "DELETE FROM CONFIG_FILTER_GROUP WHERE ID = ?"
    return update_by_sql(sql, (groupid,))


# 删除规则
def delete_filterrule(ruleid):
    sql = "DELETE FROM CONFIG_FILTER_RULES WHERE ID = ?"
    return update_by_sql(sql, (ruleid,))


# 新增规则
def insert_filter_rule(ruleid, item):
    if ruleid:
        sql = "UPDATE CONFIG_FILTER_RULES " \
              "SET ROLE_NAME=?,PRIORITY=?,INCLUDE=?,EXCLUDE=?,SIZE_LIMIT=? " \
              "WHERE ID=?"
        return update_by_sql(sql, (item.get("name"),
                                   item.get("pri"),
                                   item.get("include"),
                                   item.get("exclude"),
                                   item.get("size"),
                                   ruleid))
    else:
        sql = "INSERT INTO CONFIG_FILTER_RULES " \
              "(GROUP_ID, ROLE_NAME, PRIORITY, INCLUDE, EXCLUDE, SIZE_LIMIT)" \
              "VALUES (?, ?, ?, ?, ?, ?)"
        return update_by_sql(sql, (item.get("group"),
                                   item.get("name"),
                                   item.get("pri"),
                                   item.get("include"),
                                   item.get("exclude"),
                                   item.get("size")))
