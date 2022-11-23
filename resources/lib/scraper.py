# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher scraping engine for Googlesearch.

# Copyright (c) 2020-2021 Chrisism
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import logging
import json
import re
from urllib.parse import quote_plus

# --- AKL packages ---
from akl import constants, settings
from akl.utils import io, net, kodi
from akl.scrapers import Scraper
from akl.api import ROMObj


# ------------------------------------------------------------------------------------------------
# Google image search: simple free search
#
# ------------------------------------------------------------------------------------------------       
class GoogleImageSearch(Scraper):
    
    # --- Constructor ----------------------------------------------------------------------------
    def __init__(self):
        # --- Misc stuff ---
        self.cache_candidates = {}
        self.cache_metadata = {}
        self.cache_assets = {}
        self.all_asset_cache = {}
        
        self.regex_clean_url_key = re.compile(r'key=(.*?)(^|&)')
        self.regex_clean_url_cx = re.compile(r'cx=(.*?)(^|&)')
        
        self.logger = logging.getLogger(__name__)
        
        self.api_key = settings.getSetting("google_api_key")
        self.search_engine_id = settings.getSetting("search_engine_id")
        cache_dir = settings.getSettingAsFilePath('scraper_cache_dir')
        
        super(GoogleImageSearch, self).__init__(cache_dir)

    # --- Base class abstract methods ------------------------------------------------------------
    def get_name(self): return 'Google Image Search'

    def get_filename(self):
        return 'GoogleImageSearch'

    def supports_disk_cache(self):
        return True

    def supports_search_string(self):
        return True

    def supports_metadata_ID(self, metadata_ID):
        return False

    def supports_metadata(self):
        return False

    def supports_asset_ID(self, asset_ID): 
        return True

    def supports_assets(self):
        return True

    def check_before_scraping(self, status_dic): return

    def get_candidates(self, search_term:str, rom:ROMObj, platform, status_dic):
        # --- If scraper is disabled return immediately and silently ---
        if self.scraper_disabled:
            # If the scraper is disabled return None and do not mark error in status_dic.
            self.logger.debug('Scraper disabled. Returning empty data.')
            return None

        # Prepare data for scraping.
        # --- Request is not cached. Get candidates and introduce in the cache ---
        self.logger.debug(f'search_term          "{search_term}"')
        self.logger.debug(f'AKL platform         "{platform}"')
        candidate_list = self._search_candidates(search_term, platform, status_dic)
        if not status_dic['status']: return None

        return candidate_list

    # GoogleImageSearch does not support metadata
    def get_metadata(self, status_dic): return None

    # This function may be called many times in the ROM Scanner.
    # See comments for this function in the Scraper abstract class.
    def get_assets(self, asset_info_id, status_dic):
        # --- If scraper is disabled return immediately and silently ---
        if self.scraper_disabled:
            self.logger.debug('Scraper disabled. Returning empty data.')
            return []

        self.logger.debug(f'Getting assets {asset_info_id} for candidate ID "{self.candidate["id"]}"')

        asset_specific_cache_key = f'{self.cache_key}_{asset_info_id}'
        # --- Cache hit ---
        if self._check_disk_cache(Scraper.CACHE_INTERNAL, asset_specific_cache_key):
            self.logger.debug(f'Internal cache hit "{asset_specific_cache_key}"')
            return self._retrieve_from_disk_cache(Scraper.CACHE_INTERNAL, asset_specific_cache_key)

        # --- Cache miss. Retrieve data and update cache ---
        self.logger.debug(f'Internal cache miss "{asset_specific_cache_key}"')
        
        asset_list = []
        if asset_info_id == constants.ASSET_TRAILER_ID:
            asset_list = self._retrieve_youtube_assets(self.candidate, asset_info_id, status_dic)
        else:
            asset_list = self._retrieve_assets(self.candidate, asset_info_id, status_dic)
        
        if not status_dic['status']: 
            return None
        if asset_list is None:
            asset_list = []

        self.logger.debug(
            f"A total of {len(asset_list)} assets found for candidate ID {self.candidate['id']}"
        )

        # --- Put metadata in the cache ---
        self.logger.debug(f'Adding to internal cache "{asset_specific_cache_key}"')
        self._update_disk_cache(Scraper.CACHE_INTERNAL, asset_specific_cache_key, asset_list)
        return asset_list

    # GoogleImageSearch returns both the asset thumbnail URL and the full resolution URL so in
    # this scraper this method is trivial.
    def resolve_asset_URL(self, selected_asset, status_dic):
        url = selected_asset['url']
        url_log = self._clean_URL_for_log(url)
        return url, url_log

    def resolve_asset_URL_extension(self, selected_asset, image_url, status_dic):
        if selected_asset['asset_ID'] == constants.ASSET_TRAILER_ID:
            return "url"
        return io.get_URL_extension(image_url)

    # --- Retrieve list of games ---
    def _search_candidates(self, search_term, platform, status_dic):
        # --- Retrieve JSON data with list of games ---
        search_string_encoded = quote_plus(search_term)
        search_string_encoded = search_string_encoded + '+{}'

        google_url = ("https://customsearch.googleapis.com/customsearch/v1"
               f"?cx={self.search_engine_id}&q={search_string_encoded}"
               f"&searchType=image&key={self.api_key}&start={{}}")

        youtube_url = ("https://youtube.googleapis.com/youtube/v3/"
                f"search?part=snippet&maxResults={{}}&q={{}}&videoType=any&key={self.api_key}")

        # --- Parse game list ---
        candidate_list = []
        candidate = self._new_candidate_dic()
        candidate['id'] = search_term
        candidate['display_name'] = search_term
        candidate['platform'] = platform
        candidate['scraper_platform'] = platform
        candidate['order'] = 1
        candidate['url'] = google_url
        candidate['url_trailer'] = youtube_url
        candidate_list.append(candidate)

        return candidate_list

    def _retrieve_assets(self, candidate, asset_info_id, status_dic):
        self.logger.debug(f'Getting {asset_info_id}...')
        if asset_info_id == constants.ASSET_FANART_ID:
            asset_info_term = 'wallpaper'
        elif asset_info_id == constants.ASSET_SNAP_ID:
            asset_info_term = 'screenshot'
        elif asset_info_id == constants.ASSET_TITLE_ID:
            asset_info_term = 'title+screen'
        else:
            asset_info_term = asset_info_id
        
        url = candidate['url']
        search_results = []
        json_data = None
        for i in [1, 11, 21, 31]:
            if json_data and json_data["queries"]["nextPage"] != i:
                break

            url = url.format(asset_info_term, i)
            json_data = self._retrieve_URL_as_JSON(url, status_dic)
            if not search_results and (not json_data or not status_dic['status']): 
                self.logger.warning('No data could be retrieved from the results page')
                return

            search_results.extend(json_data["items"])

        self._dump_json_debug('GoogleImageSearch_retrieve_assets.json', search_results)

        # --- Parse images page data ---
        asset_list = []
        for search_result in search_results:
            try:
                asset_data = self._new_assetdata_dic()
                asset_data['asset_ID'] = asset_info_id
                asset_data['display_name'] = search_result['title']
                asset_data['url_thumb'] = search_result['image']["thumbnailLink"]
                asset_data['url'] = search_result['link']

                if self.verbose_flag: 
                    self.logger.debug(f"Found asset {asset_data['url_thumb']}")
                asset_list.append(asset_data)    
            except Exception:
                self.logger.exception('Error while parsing single result.')
                if self.verbose_flag: 
                    self.logger.error(f'Failed result: {json.dumps(search_result)}')
                
        self.logger.debug(
            f"Found {len(asset_list)} assets for candidate #{candidate['id']} of type {asset_info_id}"
        )
        return asset_list
    
    def _retrieve_youtube_assets(self, candidate, asset_info_id, status_dic):
        self.logger.debug(f'Getting {asset_info_id}...')
        
        url = candidate['url_trailer']
        url = url.format(40, asset_info_id)

        json_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not json_data or not status_dic['status']: 
            self.logger.warning('No data could be retrieved from the results page')
            return

        self._dump_json_debug('GoogleImageSearch_retrieve_assets.json', json_data)
        search_results = json_data["items"]

        # --- Parse images page data ---
        asset_list = []
        for search_result in search_results:
            try:
                yt_id = search_result['id']['videoId']
                asset_data = self._new_assetdata_dic()
                asset_data['asset_ID'] = asset_info_id
                asset_data['display_name'] = search_result['snippet']['title']
                asset_data['url_thumb'] = search_result['snippet']['thumbnails']['default']['url']
                asset_data['url'] = f"plugin://plugin.video.youtube/play/?video_id={yt_id}"

                if self.verbose_flag: 
                    self.logger.debug(f"Found asset {asset_data['url_thumb']}")
                asset_list.append(asset_data)    
            except Exception:
                self.logger.exception('Error while parsing single result.')
                if self.verbose_flag: 
                    self.logger.error(f'Failed result: {json.dumps(search_result)}')
                
        self.logger.debug(
            f"Found {len(asset_list)} assets for candidate #{candidate['id']} of type {asset_info_id}"
        )
        return asset_list

    # Google URLs have the API key and searchengine id.
    # Clean URLs for safe logging.
    def _clean_URL_for_log(self, url):
        clean_url = url
        clean_url = self.regex_clean_url_key.sub(r'key=***\2', clean_url)
        clean_url = self.regex_clean_url_cx.sub(r'cx=***\2', clean_url)

        return clean_url

    # Retrieve URL and create a JSON object.
    # GoogleImageSearch
    #
    def _retrieve_URL_as_JSON(self, url, status_dic, retry=0):
        http_code = 200
        url_log = self._clean_URL_for_log(url)
        json_data = net.get_URL_as_json(url, url_log)
        
        if "error" in json_data:
            http_code = json_data["error"]["code"]
            error_msg = json_data["error"]["message"]
            self.logger.error(f"Error while calling Google API: {error_msg}")

        # --- Check Response error codes ---
        if http_code == 400:
            self._handle_error(status_dic, f'Bad HTTP status code {http_code}')
            return None
        elif http_code == 429:
            self.logger.debug('HTTP status 429: Limit exceeded.')
            kodi.notify_warn("API limit reached")
            return None
        elif http_code == 404:
            self.logger.debug('HTTP status 404: no candidates found.')
            return None
        elif http_code != 200:
            # Unknown HTTP status code.
            self._handle_error(status_dic, f'Bad HTTP status code {http_code}')
            return None

        return json_data