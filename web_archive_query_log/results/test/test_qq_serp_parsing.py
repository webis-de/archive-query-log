# This file is auto-generated by generate_tests.py. 
from web_archive_query_log.results.test.test_utils import verify_serp_parsing


def test_parse_query_qq_danil_kozlovsky_1360453772():
    verify_serp_parsing(
        "https://web.archive.org/web/20130210004932id_/http://v.qq.com/search.html?pagetype=3&stag=word.tag&ms_key=danil%20kozlovsky",
        "qq",
    )


def test_parse_query_qq_feng_mi_lian_1380895166():
    verify_serp_parsing(
        "https://web.archive.org/web/20131004155926id_/http://v.qq.com/search.html?pagetype=3&stag=word.tag&ms_key=%E5%B3%B0%E5%B9%82%E6%81%8B",
        "qq",
    )


def test_parse_query_qq_ji_lin_yan_ji_1360789033():
    verify_serp_parsing(
        "https://web.archive.org/web/20130213215713id_/http://v.qq.com:80/search.html?pagetype=3&ms_key=%E5%90%89%E6%9E%97%E5%BB%B6%E5%90%89",
        "qq",
    )


def test_parse_query_qq_zhong_nian_wei_ji_1408289827():
    verify_serp_parsing(
        "https://web.archive.org/web/20140817173707id_/http://v.qq.com/search.html?pagetype=3&stag=word.tag&ms_key=%E4%B8%AD%E5%B9%B4%E5%8D%B1%E6%9C%BA",
        "qq",
    )


def test_parse_query_qq_jie_ke_luo_de_wei_er_1445892389():
    verify_serp_parsing(
        "https://web.archive.org/web/20151026214629id_/http://v.qq.com/search.html?pagetype=3&stag=txt.playpage.sports&ms_key=%E6%9D%B0%E5%85%8B.%E7%BD%97%E5%BE%B7%E7%BB%B4%E5%B0%94",
        "qq",
    )
