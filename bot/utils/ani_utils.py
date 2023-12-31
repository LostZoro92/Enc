import string

import anitopy
import country_converter as coco
import flag
import pycountry
import requests

from bot import C_LINK, CAP_DECO, parse_file, release_name, release_name_b

from .bot_utils import auto_rename, crc32, get_codec, text_filter, txt_to_str
from .log_utils import log, logger
from .os_utils import file_exists, get_stream_info, info, p_dl

ar_file = "Auto-rename.txt"
filter_file = "filter.txt"
url = "https://graphql.anilist.co"

anime_query = """
query ($id: Int, $idMal:Int, $search: String, $type: MediaType, $asHtml: Boolean) {
  Media (id: $id, idMal: $idMal, search: $search, type: $type) {
    id
    idMal
    title {
      romaji
      english
      native
    }
    format
    status
    description (asHtml: $asHtml)
    startDate {
      year
      month
      day
    }
    season
    episodes
    duration
    countryOfOrigin
    source (version: 2)
    trailer {
      id
      site
      thumbnail
    }
    coverImage {
      extraLarge
    }
    bannerImage
    genres
    averageScore
    nextAiringEpisode {
      airingAt
      timeUntilAiring
      episode
    }
    isAdult
    characters (role: MAIN, page: 1, perPage: 10) {
      nodes {
        id
        name {
          full
          native
        }
        image {
          large
        }
        description (asHtml: $asHtml)
        siteUrl
      }
    }
    studios (isMain: true) {
      nodes {
        name
        siteUrl
      }
    }
    siteUrl
  }
}
"""


async def get_cus_tag(fn, rg, caption=False):
    release_tag, file_tag, caption_tag = None, str(), None
    file_filter, release_filter, caption_filter = await text_filter()
    if release_filter and rg:
        for item in release_filter.split("\n"):
            if len(item.split("|")) <= 2:
                continue
            check, out, out1 = item.split("|")
            out = out1 if caption else out
            if check.casefold() != rg.casefold():
                continue
            if out.casefold() == "disable":
                break
            release_tag = out
            break

    if file_filter:
        for item in file_filter.split("\n"):
            if len(item.split("|")) <= 2:
                continue
            check, out, out1 = item.split("|")
            out = out1 if caption else out
            if check.startswith("^"):
                if not check.lstrip("^") in fn:
                    continue
                if out.casefold() == "disable":
                    break
            else:
                if not check.casefold() in fn.casefold():
                    continue
            if out.casefold() == "disable":
                continue
            file_tag += out
            if check.startswith("^"):
                break
            if not caption:
                break
            file_tag += " "

    if caption_filter and caption:
        for item in caption_filter.split("\n"):
            if len(item.split("||")) < 2:
                continue
            _check_r, _check_i = item.split("||", maxsplit=1)
            if _check_r != rg:
                continue
            for items in _check_i.split("||"):
                if len(items.split("|")) < 2:
                    continue
                check, out = items.split("|")
                if check in fn:
                    caption_tag = out
                    break

    final_output = release_tag
    if caption_tag:
        final_output = (
            caption_tag + " : " + final_output if final_output else caption_tag
        )

    return file_tag.strip() if not final_output else final_output


async def get_file_tag(_infile, caption=False):
    _ainfo, _sinfo = await get_stream_info(_infile)
    if not caption:
        if _ainfo:
            if len(_ainfo.split("|")) > 3:
                out = "MULTi"
            elif len(_ainfo.split("|")) == 3:
                out = "Tri"
            elif len(_ainfo.split("|")) == 2:
                out = "Dual"
            else:
                out = None
        elif _ainfo is None:
            out = "TBD"
    else:
        if _ainfo or _sinfo:
            out = ""
            if _ainfo:
                audio_count = len(_ainfo.split("|"))
                if audio_count > 3:
                    out += f"(Multi-Audio)[{audio_count}] "
                elif audio_count == 3:
                    out += "(Tri-Audio) "
                elif audio_count == 2:
                    out += f"(Dual-Audio) "
            if _sinfo:
                subs = _sinfo.split("|")
                sub_count = len(subs)
                if sub_count > 2:
                    out += f"(Multi-Subs)[{sub_count}]"
                elif sub_count > 1:
                    __dual = False
                    if _ainfo and audio_count == 2:
                        if subs[0] == "eng" and subs[0] == subs[1]:
                            __dual = True
                    if not __dual:
                        if subs[0] != subs[1]:
                            out += f"({subs[0]} & {subs[1]} subs)"
                        else:
                            out += f"({subs[0].title()}-subs)"
                else:
                    __dual = False
                    if _ainfo and audio_count == 2:
                        if _sinfo == "eng":
                            __dual = True
                    if not __dual:
                        out += f"({_sinfo.title()}-sub)"
        else:
            out = "(English subtitle)"
    return out


def get_flag(lang_t):
    if not lang_t == "?":
        if "-" in lang_t:
            lang_t1, lang_t2 = lang_t.split("-", maxsplit=1)
            if lang_t2.isdigit():
                lang_t = lang_t1
            else:
                lang_t = lang_t2
        if lang_t.casefold() == "eng":
            lang_t = "US"
        elif lang_t.casefold() == "ara":
            lang_t = "Arabia"
        elif lang_t.casefold() == "hin":
            lang_t = "ind"
        elif lang_t.casefold() == "ind":
            lang_t = "Indonesia"
        lang_t = pycountry.countries.search_fuzzy(lang_t)
        lang_t = lang_t[0].alpha_2
        lang_t = flag.flag(lang_t)
    return lang_t


async def filter_name(name, _filter):
    fil1 = fil2 = fil3 = str()
    try:
        if _filter:
            fil = _filter.strip("\n")
            if len(fil.split("\n")) < 3:
                raise Exception("Malformed filter!")
            fil1, fil2, fil3 = fil.split("\n")

        elif file_exists(filter_file):
            with open(filter_file, "r") as file:
                fil = file.read().strip("\n")
            if len(fil.split("\n")) < 3:
                raise Exception("Malformed filter!")
            fil1, fil2, fil3 = fil.split("\n")

        if fil1 and fil1.casefold() != "disable":
            for i in fil1.split("|"):
                name = name.replace(i, "")
        if fil2.casefold() == "disable":
            fil2 = None
        if fil3.casefold() == "disable":
            fil3 = None
    except Exception:
        await logger(Exception)

    return name, fil2, fil3


async def conconvert(iso2_codes):
    try:
        iso3_codes = coco.convert(names=iso2_codes, to="ISO3").capitalize()
    except Exception:
        log(Exception)
    return iso3_codes


async def parse(
    name,
    _file=None,
    _ext=".mkv",
    anilist=True,
    cust_con=None,
    v=None,
    folder="downloads/",
    _filter=None,
):
    try:
        _parsed = anitopy.parse(name)
        name, fil2, fil3 = await filter_name(name, _filter)

        ## Get info ##
        parsed = anitopy.parse(name)
        # title
        title = parsed.get("anime_title")
        # original title without the effects of filter
        or_title = _parsed.get("anime_title")
        # episode number
        epi = parsed.get("episode_number")
        # season number
        sn = parsed.get("anime_season")
        if sn and sn.startswith("0"):
            sn = str(int(sn))
        if sn == "1":
            sn = None
        # release group
        rg = parsed.get("release_group")
        # release information
        ri = f'[{parsed.get("release_information")}]'
        # year
        yr = parsed.get("anime_year")
        # episode title
        et = parsed.get("episode_title")
        not_allowed = "END", "MULTi"
        et = None if et in not_allowed else et
        # source
        sor = parsed.get("source")

        if title is None:
            raise Exception("Parsing Failed")
        title = f"{title} {yr}" if yr else title
        _file = name if not _file else _file
        _infile = folder + _file
        r_is_end = True if ri == "[END]" else False
        codec = await get_codec()
        con = None

        try:
            if file_exists(parse_file) or not anilist:
                raise Exception("Anilist parsing Turned off")
            variables = {"search": title, "type": "ANIME"}
            json = (
                requests.post(url, json={"query": anime_query, "variables": variables})
                .json()["data"]
                .get("Media")
            )
            title = json["title"]["english"]
            title = json["title"]["romaji"] if not title else title
            con = f"{json['countryOfOrigin']}"
            con = await conconvert(con)
            te = f"{json.get('episodes')}"
            te = "0" + str(te) if epi.startswith("0") else te
            title = string.capwords(title)
        except Exception:
            # log(Exception)
            te = None

        a_con = await get_file_tag(_infile)
        a_con = await get_cus_tag(name, rg) if not a_con else a_con
        a_con = con if not a_con else a_con
        a_con = fil2 if (fil2 and fil2.casefold() != "auto") or fil2 is None else a_con

        a_con = cust_con if cust_con else a_con

        if len(title) > 33:
            f_title = title[:32] + "…"
            f_title = f_title.split(":")[0]
        else:
            f_title = title

        ar = txt_to_str(ar_file)
        f_title = await auto_rename(f_title, or_title, ar)

        file_name = str()
        file_name += release_name
        file_name += " "
        file_name += f_title
        if sn:
            file_name += " S"
            file_name += sn
        if epi:
            file_name += " - "
            file_name += epi
        if v:
            file_name += f"v{v}"
        if ((te and te == epi) and not sn) or r_is_end:
            file_name += " [END]"
        if a_con:
            file_name += f" [{a_con}]"
        file_name2 = file_name.replace(f_title, title)
        file_name2 = file_name2.replace(release_name, release_name_b)
        if codec:
            file_name2 += " "
            file_name2 += codec
        if sor:
            file_name2 += sor
        file_name += ".mkv"
    except Exception:
        await logger(Exception)
        file_name = _file.replace(f".{_ext}", f" {C_LINK}.{_ext}")
        file_name2 = file_name
    if "/" in file_name:
        file_name = file_name.replace("/", " ")
    return file_name, file_name2


async def dynamicthumb(name, thum="thumb2.jpg", anilist=True, _filter=None):
    try:
        name, fil2, fil3 = await filter_name(name, _filter)
        ## Get info ##
        parsed = anitopy.parse(name)
        # title
        title = parsed.get("anime_title")
        # episode number
        epi = parsed.get("episode_number")
        # season number
        sn = parsed.get("anime_season")
        if sn and sn.startswith("0"):
            sn = str(int(sn))
        if sn == "1":
            sn = None
        # release group
        rg = parsed.get("release_group")
        if file_exists(parse_file) or not anilist:
            raise Exception("Parsing turned off")
        try:
            variables = {"search": title, "type": "ANIME"}
            json = (
                requests.post(url, json={"query": anime_query, "variables": variables})
                .json()["data"]
                .get("Media")
            )
            t_title = json["title"]["english"]
            t_title = json["title"]["romaji"] if not t_title else t_title
        except Exception:
            t_title = title
        s_title = t_title
        if sn:
            s_title += " " + sn
        try:
            variables = {"search": s_title, "type": "ANIME"}
            json = (
                requests.post(url, json={"query": anime_query, "variables": variables})
                .json()["data"]
                .get("Media")
            )
            link = json.get("coverImage")["extraLarge"]
        except Exception:
            try:
                variables = {"search": title, "type": "ANIME"}
                json = (
                    requests.post(
                        url, json={"query": anime_query, "variables": variables}
                    )
                    .json()["data"]
                    .get("Media")
                )
                link = json.get("coverImage")["extraLarge"]
            except Exception:
                pass
                # await logger(Exception)
        p_dl(link, thum)
    except Exception:
        pass
        # log(Exception)
    return title, epi, sn, rg


async def custcap(
    name,
    fname,
    anilist=True,
    cust_type=None,
    folder="encode/",
    ccd=None,
    ver=None,
    encoder=None,
    _filter=None,
):
    try:
        name, fil2, fil3 = await filter_name(name, _filter)
        ## Get info ##
        parsed = anitopy.parse(name)
        # title
        title = parsed.get("anime_title")
        # episode number
        epi = parsed.get("episode_number")
        # season number
        sn = parsed.get("anime_season")
        if sn and sn.startswith("0"):
            sn = str(int(sn))
        if sn == "1":
            sn = None
        # release group
        rg = parsed.get("release_group")
        # release information
        ri = parsed.get("release_information")
        ri = f"[{ri}]" if ri else ri
        # year
        yr = parsed.get("anime_year")
        # episode title
        et = parsed.get("episode_title")
        not_allowed = "END", "MULTi", "WEB"
        et = None if et in not_allowed else et
        # source
        sor = parsed.get("source")

        if title is None:
            raise Exception("Parsing Failed")
        out = folder + fname
        ccd = CAP_DECO if not ccd else ccd
        or_title = title
        r_is_end = True if ri == "[END]" else False
        codec = await get_codec()
        cap_info = await get_cus_tag(name, rg, True)
        cap_info = await get_file_tag(out, True) if not cap_info else cap_info

        auto = cap_info
        cap_info = (
            fil3 if (fil3 and fil3.casefold() != "auto") or fil3 is None else cap_info
        )
        cap_info = cust_type if cust_type else cap_info
        te = None
        try:
            if file_exists(parse_file) or not anilist:
                raise Exception("Parsing turned off")
            variables = {"search": title, "type": "ANIME"}
            json = (
                requests.post(url, json={"query": anime_query, "variables": variables})
                .json()["data"]
                .get("Media")
            )
            title = json["title"]["english"]
            title = json["title"]["romaji"] if not title else title
            if sn:
                variables = {"search": f"{title} {sn}", "type": "ANIME"}
                json = (
                    requests.post(
                        url, json={"query": anime_query, "variables": variables}
                    )
                    .json()["data"]
                    .get("Media")
                )
            te = str(json.get("episodes"))
            te = "0" + str(te) if epi.startswith("0") else te
        except Exception:
            log(Exception)

        title = string.capwords(title)
        ar = txt_to_str(ar_file)
        title = await auto_rename(title, or_title, ar, caption=True)
        crc32s, mi = None, None
        if file_exists(out):
            crc32s = await crc32(out)
            mi = await info(out)

        caption = f"**{ccd} Title:** `{title}`\n"
        if epi:
            caption += f"**{ccd} Episode:** `{epi}`"
        if ver:
            caption += f" (v{ver})"
            if not epi:
                caption += "\n"
        if epi:
            caption += "\n"
        if sn:
            caption += f"**{ccd} Season:** `{sn}`\n"
        if cap_info and mi:
            cap_info = cap_info.format(**locals())
            caption += f"**{ccd} Type:** [{cap_info.strip()}]({mi})"
        elif cap_info:
            cap_info = cap_info.format(**locals())
            caption += f"**{ccd} Type:** `{cap_info.strip()}`"
        if not r_is_end and ri:
            caption += f" `{ri}`"
        if epi == te or r_is_end:
            caption += " **[END]**\n"
        else:
            caption += "\n"
        if et:
            caption += f"**{ccd} Episode Title:** `{et}`\n"
        if codec:
            caption += f"**🌟:** `{codec}`"
            if sor:
                caption += f" `[{sor}]`"
            caption += "\n"
        if encoder:
            encr = encoder.replace("@", "", 1)
            caption += f"**{ccd} Encoder:** `{encr}`\n"
        caption += f"**{ccd} CRC32:** `[{crc32s}]`\n"
        caption += f"**🔗 {C_LINK}**"
    except Exception:
        await logger(Exception)
        om = fname.split(".")[0]
        ot = om.split("@")[0]
        caption = f"**{ot}**\n**🔗 {C_LINK}**"
    return caption


async def qparse(name, ver=None, fil=None):
    return (await parse(name, v=ver, _filter=fil))[0]


async def f_post(name, out, fcodec=None, mi=None, _filter=None):
    try:
        name = (await filter_name(name, _filter))[0]
        ## Get info ##
        parsed = anitopy.parse(name)
        # title
        title = parsed.get("anime_title")
        # episode number
        epi = parsed.get("episode_number")
        # season number
        sn = parsed.get("anime_season")
        # release group
        rg = parsed.get("release_group")
        if sn and sn.startswith("0"):
            sn = str(int(sn))
        if sn == "1":
            sn = None

        codec = fcodec if fcodec else await get_codec()

        try:
            if file_exists(parse_file):
                raise Exception("Parsing turned off")
            s_title = title
            if sn:
                s_title = title + " " + sn
            variables = {"search": title, "type": "ANIME"}
            json = (
                requests.post(url, json={"query": anime_query, "variables": variables})
                .json()["data"]
                .get("Media")
            )
            variables = {"search": s_title, "type": "ANIME"}
            json2 = (
                requests.post(url, json={"query": anime_query, "variables": variables})
                .json()["data"]
                .get("Media")
            )
            title = json["title"]["english"]
            title = json["title"]["romaji"] if title is None else title
            title_r = json["title"]["romaji"]
            try:
                id_ = json2["id"]
            except Exception:
                id_ = json["id"]
            pic_url = f"https://img.anili.st/media/{id_}"
            con = f"{json['countryOfOrigin']}"
            gen = json.get("genres")
            genre = str()

        except Exception:
            title_r = "N/A"
            cflag = con = "?"
            gen = None
            pic_url = "https://upload.wikimedia.org/wikipedia/commons/d/d1/Image_not_available.png"
        a_lang = ""
        s_lang = ""

        _ainfo, _sinfo = await get_stream_info(out)
        if _ainfo:
            for a_lang_t in _ainfo.split("|"):
                a_lang += get_flag(a_lang_t)
                a_lang += ", "
            a_lang = a_lang.strip(", ")
        else:
            a_lang = "N/A"
        if _sinfo:
            for s_lang_t in _sinfo.split("|"):
                s_lang += get_flag(s_lang_t)
                s_lang += ", "
            s_lang = s_lang.strip(", ")
        else:
            s_lang = "N/A"

        cflag = flag.flag(con) if not con == "?" else con
        if gen:
            for x in gen:
                genre += "#" + (x.replace(" ", "_")).replace("-", "_") + " "

        msg = f"[{cflag}]"
        if title == title_r:
            msg += f"`{title}`"
        else:
            msg += f"**{title_r}** | `{title}`"
        msg += "\n\n"
        if rg or mi:
            msg += f"**Source:** **[[{rg}]]({mi})**"
            msg += "\n\n"
        if gen and genre:
            msg += f"**‣ Genre** : {genre}\n"
        if epi:
            msg += f"**‣ Episode** : `{epi}`\n"
        if sn:
            msg += f"**‣ Season** : `{sn}`\n"
        msg += f"**‣ Quality** : `{codec}`\n"
        msg += f"**‣ Audio(s)** : `{a_lang}`\n"
        msg += f"**‣ Subtitle(s)** : `{s_lang}`\n"
    except Exception:
        pic_url = None
        msg = None
        await logger(Exception)
    return pic_url, msg
