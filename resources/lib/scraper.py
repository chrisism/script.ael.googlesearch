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
from datetime import datetime, timedelta

# --- AEL packages ---
from ael import constants, settings
from ael.utils import io, net, kodi
from ael.scrapers import Scraper
from ael.api import ROMObj

logger = logging.getLogger(__name__)

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
        
        cache_dir = settings.getSetting('scraper_cache_dir')
        super(GoogleImageSearch, self).__init__(cache_dir)

    # --- Base class abstract methods ------------------------------------------------------------
    def get_name(self): return 'Google Image Search'

    def get_filename(self): return 'GoogleImageSearch'

    def supports_disk_cache(self): return True

    def supports_search_string(self): return True

    def supports_metadata_ID(self, metadata_ID): return False

    def supports_metadata(self): return False

    def supports_asset_ID(self, asset_ID): 
        return asset_ID != constants.ASSET_TRAILER_ID

    def supports_assets(self): return True

    def check_before_scraping(self, status_dic): return

    def get_candidates(self, search_term:str, rom:ROMObj, platform, status_dic):
        # --- If scraper is disabled return immediately and silently ---
        if self.scraper_disabled:
            # If the scraper is disabled return None and do not mark error in status_dic.
            logger.debug('GoogleImageSearch.get_candidates() Scraper disabled. Returning empty data.')
            return None

        # Prepare data for scraping.
        # --- Request is not cached. Get candidates and introduce in the cache ---
        logger.debug('GoogleImageSearch.get_candidates() search_term          "{0}"'.format(search_term))
        logger.debug('GoogleImageSearch.get_candidates() AEL platform         "{0}"'.format(platform))
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
            logger.debug('GoogleImageSearch.get_assets() Scraper disabled. Returning empty data.')
            return []

        logger.debug('GoogleImageSearch.get_assets() Getting assets {} for candidate ID "{}"'.format(
            asset_info_id, self.candidate['id']))

        asset_specific_cache_key = '{}_{}'.format(self.cache_key, asset_info_id)
        # --- Cache hit ---
        if self._check_disk_cache(Scraper.CACHE_INTERNAL, asset_specific_cache_key):
            logger.debug('GoogleImageSearch.get_assets() Internal cache hit "{0}"'.format(asset_specific_cache_key))
            return self._retrieve_from_disk_cache(Scraper.CACHE_INTERNAL, asset_specific_cache_key)

        # --- Cache miss. Retrieve data and update cache ---
        logger.debug('GoogleImageSearch.get_assets() Internal cache miss "{0}"'.format(asset_specific_cache_key))
        
        asset_list = self._retrieve_assets(self.candidate, asset_info_id, status_dic)
        if not status_dic['status']: return None
        logger.debug('GoogleImageSearch::get_assets()  A total of {} assets found for candidate ID {}'.format(len(asset_list), self.candidate['id']))

        # --- Put metadata in the cache ---
        logger.debug('GoogleImageSearch.get_assets() Adding to internal cache "{0}"'.format(asset_specific_cache_key))
        self._update_disk_cache(Scraper.CACHE_INTERNAL, asset_specific_cache_key, asset_list)
        return asset_list

    # GoogleImageSearch returns both the asset thumbnail URL and the full resolution URL so in
    # this scraper this method is trivial.
    def resolve_asset_URL(self, selected_asset, status_dic):
        url = selected_asset['url']
        return url, url

    def resolve_asset_URL_extension(self, selected_asset, image_url, status_dic):
        return io.get_URL_extension(image_url)

    def download_image(self, image_url, image_local_path: io.FileName):
        self._wait_for_API_request(100)
        # net_download_img() never prints URLs or paths.
        net.download_img(image_url, image_local_path)
        
        # failed? retry after 5 seconds
        if not image_local_path.exists():
            logger.debug('Download failed. Retry after 5 seconds')
            self._wait_for_API_request(5000)
            net.download_img(image_url, image_local_path)
        return image_local_path

    # --- Retrieve list of games ---
    def _search_candidates(self, search_term, platform, status_dic):
        # --- Retrieve JSON data with list of games ---
        search_string_encoded = quote_plus(search_term)
        search_string_encoded = search_string_encoded + '+{}'
        url = 'https://www.google.com/search?q={}&source=lnms&tbm=isch'.format(search_string_encoded)

        # --- Parse game list ---
        candidate_list = []
        candidate = self._new_candidate_dic()
        candidate['id'] = search_term
        candidate['display_name'] = search_term
        candidate['platform'] = platform
        candidate['scraper_platform'] = platform
        candidate['order'] = 1
        candidate['url'] = url
        candidate_list.append(candidate)

        return candidate_list

    def _retrieve_assets(self, candidate, asset_info_id, status_dic):
        logger.debug('GoogleImageSearch._retrieve_assets() Getting {}...'.format(asset_info_id))
        if asset_info_id == constants.ASSET_FANART_ID:
            asset_info_term = 'wallpaper'
        elif asset_info_id == constants.ASSET_SNAP_ID:
            asset_info_term = 'screenshot'
        elif asset_info_id == constants.ASSET_TITLE_ID:
            asset_info_term = 'title+screen'
        else:
            asset_info_term = asset_info_id
        
        url = candidate['url'].format(asset_info_term)
        json_data = self._retrieve_URL_as_JSON(url, status_dic)
        if not json_data or not status_dic['status']: 
            logger.warning('No data could be retrieved from the results page')
            return None
        self._dump_json_debug('GoogleImageSearch_retrieve_assets.json', json_data)

        # --- Parse images page data ---
        asset_list = []
        search_results = json_data['data'][31][0][12][2]
        for search_result in search_results:
            try:
                image_data = search_result[1][3]
                thumb_data = search_result[1][2]
                image_info = search_result[1][9]
                
                asset_data = self._new_assetdata_dic()
                asset_data['asset_ID'] = asset_info_id
                asset_data['display_name'] = image_info['2003'][3] if image_info else ''
                asset_data['url_thumb'] = thumb_data[0].replace('q\u003d', 'q=')
                asset_data['url'] = image_data[0]
                if self.verbose_flag: logger.debug('Found asset {0}'.format(asset_data['url_thumb']))
                asset_list.append(asset_data)    
            except Exception as ex:
                logger.error('Error while parsing single result.')
                if self.verbose_flag: logger.error('Failed result: {}'.format(json.dumps(search_result)))
                
        logger.debug('GoogleImageSearch._retrieve_assets() Found {} assets for candidate #{} of type {}'.format(
            len(asset_list), candidate['id'], asset_info_id))

        return asset_list
    
    # Retrieve URL and create a JSON object.
    # GoogleImageSearch
    #
    def _retrieve_URL_as_JSON(self, url, status_dic, retry=0):
        self._wait_for_API_request(50)
        page_data_raw, http_code = net.get_URL(url, url)
        self.last_http_call = datetime.now()

        # --- Check HTTP error codes ---
        if http_code == 400:
            # Code 400 describes an error. See API description page.
            logger.debug('GoogleImageSearch._retrieve_URL_as_JSON() HTTP status 400: general error.')
            self._handle_error(status_dic, 'Bad HTTP status code {}'.format(http_code))
            return None
        elif http_code == 429 and retry < Scraper.RETRY_THRESHOLD:
            logger.debug('GoogleImageSearch._retrieve_URL_as_JSON() HTTP status 429: Limit exceeded.')
            # Number of requests limit, wait at least 2 minutes. Increments with every retry.
            amount_seconds = 120*(retry+1)
            wait_till_time = datetime.now() + timedelta(seconds=amount_seconds)
            kodi.dialog_OK('You\'ve exceeded the max rate limit.', 
                           'Respecting the website and we wait at least till {}.'.format(wait_till_time))
            self._wait_for_API_request(amount_seconds*1000)
            # waited long enough? Try again
            retry_after_wait = retry + 1
            return self._retrieve_URL_as_JSON(url, status_dic, retry_after_wait)
        elif http_code == 404:
            # Code 404 means nothing found. Return None but do not mark
            # error in status_dic.
            logger.debug('GoogleImageSearch._retrieve_URL_as_JSON() HTTP status 404: no candidates found.')
            return None
        elif http_code != 200:
            # Unknown HTTP status code.
            self._handle_error(status_dic, 'Bad HTTP status code {}'.format(http_code))
            return None
        
        # Convert data to JSON.
        results = {}
        results['images'] = []

        ## looking for <script nonce="xoK1dLqTFF+mzuRvsjh/Xg">AF_initDataCallbackAF_initDataCallback({key: 'ds:2', isError:  false , hash: '3', data:[..]
        hits = re.findall(r"<script nonce=\".*\">AF_initDataCallback\({key: 'ds:\d',( isError:  false ,)? hash: '.*?', data:(.*?), sideChannel: {}}\);</script>", page_data_raw, flags=re.S)
        if len(hits) == 0: return None
        
        hit = hits[-1][-1]
        hit = '{"data": ' + hit + '}'
        try:
            return json.loads(hit)
        except Exception as ex:
            logger.error('Error creating JSON data from GoogleImageSearch.')
            self._handle_error(status_dic, 'Error creating JSON data from GoogleImageSearch.')
            return None
       