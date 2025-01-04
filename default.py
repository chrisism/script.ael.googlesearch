# -*- coding: utf-8 -*-
#
# GoogleSearch Scraper for AKL
#
# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import sys
import logging
    
# --- Kodi stuff ---
import xbmcaddon

# AKL main imports
from akl import constants, settings, addons
from akl.utils import kodilogging, io, kodi
from akl.scrapers import ScraperSettings, ScrapeStrategy

# Local modules
from resources.lib.scraper import GoogleImageSearch

kodilogging.config()
logger = logging.getLogger(__name__)

# --- Addon object (used to access settings) ---
addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')


# ---------------------------------------------------------------------------------------------
# This is the plugin entry point.
# ---------------------------------------------------------------------------------------------
def run_plugin():
    os_name = io.is_which_os()
    
    # --- Some debug stuff for development ---
    logger.info('------------ Called Advanced Kodi Launcher Plugin: Googlesearch Scraper ------------')
    logger.info(f'addon.id         "{addon_id}"')
    logger.info(f'addon.version    "{addon_version}"')
    logger.info(f'sys.platform     "{sys.platform}"')
    logger.info(f'OS               "{os_name}"')
    
    for i in range(len(sys.argv)):
        logger.info(f'sys.argv[{i}] "{sys.argv[i]}"')

    addon_args = addons.AklAddonArguments('script.akl.mobygames')
    try:
        addon_args.parse()
    except Exception as ex:
        logger.error('Exception in plugin', exc_info=ex)
        kodi.dialog_OK(text=addon_args.get_usage())
        return
    
    if addon_args.get_command() == addons.AklAddonArguments.SCRAPE:
        run_scraper(addon_args)
    elif addon_args.args.cmd == "update-settings":
        update_plugin()
    else:
        kodi.dialog_OK(text=addon_args.get_help())        
        
    logger.debug('Advanced Kodi Launcher Plugin: Googlesearch Scraper -> exit')


# ---------------------------------------------------------------------------------------------
# Scraper methods.
# ---------------------------------------------------------------------------------------------
def run_scraper(args):
    logger.debug('========== run_scraper() BEGIN ==================================================')
    pdialog = kodi.ProgressDialog()
    
    settings = ScraperSettings.from_settings_dict(args.get_settings())
    scraper_strategy = ScrapeStrategy(
        args.get_webserver_host(),
        args.get_webserver_port(),
        settings,
        GoogleImageSearch(),
        pdialog)
                  
    if args.get_entity_type() == constants.OBJ_ROM:
        scraped_rom = scraper_strategy.process_single_rom(args.get_entity_id())
        pdialog.endProgress()
        pdialog.startProgress('Saving ROM in database ...')
        scraper_strategy.store_scraped_rom(args.get_akl_addon_id(), args.get_entity_id(), scraped_rom)
        pdialog.endProgress()
    else:
        scraped_roms = scraper_strategy.process_roms(args.get_entity_type(), args.get_entity_id())
        pdialog.endProgress()
        pdialog.startProgress('Saving ROMs in database ...')
        scraper_strategy.store_scraped_roms(args.get_akl_addon_id(),
                                            args.get_entity_type(),
                                            args.get_entity_id(),
                                            scraped_roms)
        pdialog.endProgress()
        

# ---------------------------------------------------------------------------------------------
# UPDATE PLUGIN
# ---------------------------------------------------------------------------------------------
def update_plugin():
    supported_assets = '|'.join(constants.ROM_ASSET_ID_LIST)
    
    settings.setSetting("akl.scraper.supported_assets", supported_assets)
    kodi.notify("Updated AKL plugin settings for this addon")


# ---------------------------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------------------------
try:
    run_plugin()
except Exception as ex:
    logger.fatal('Exception in plugin', exc_info=ex)
    kodi.notify_error("General failure")
