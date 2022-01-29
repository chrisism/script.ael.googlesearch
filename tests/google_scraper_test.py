import unittest, os
import unittest.mock
from unittest.mock import MagicMock, patch

import json
import logging

from tests.fakes import FakeProgressDialog, random_string, FakeFile

logging.basicConfig(format = '%(asctime)s %(module)s %(levelname)s: %(message)s',
                datefmt = '%m/%d/%Y %I:%M:%S %p', level = logging.DEBUG)
logger = logging.getLogger(__name__)

from resources.lib.scraper import GoogleImageSearch
from akl.scrapers import ScrapeStrategy, ScraperSettings

from akl.api import ROMObj
from akl import constants
from akl.utils import net

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def mocked_google(url, url_log=None):

    mocked_html = ''
    if '&tbm=isch' in url:
        mocked_html = os.path.abspath(os.path.join(Test_google_scrapers.TEST_ASSETS_DIR,'google_result.html'))
    if 'youtube.com' in url:
        mocked_html = os.path.abspath(os.path.join(Test_google_scrapers.TEST_ASSETS_DIR,'youtube_result.html'))
    if mocked_html == '':
        return net.get_URL(url, url)

    print('reading mocked data from file: {}'.format(mocked_html))
    return read_file(mocked_html), 200

class Test_google_scrapers(unittest.TestCase):
    
    ROOT_DIR = ''
    TEST_DIR = ''
    TEST_ASSETS_DIR = ''

    @classmethod
    def setUpClass(cls):        
        cls.TEST_DIR = os.path.dirname(os.path.abspath(__file__))
        cls.ROOT_DIR = os.path.abspath(os.path.join(cls.TEST_DIR, os.pardir))
        cls.TEST_ASSETS_DIR = os.path.abspath(os.path.join(cls.TEST_DIR,'assets'))
                
        print('ROOT DIR: {}'.format(cls.ROOT_DIR))
        print('TEST DIR: {}'.format(cls.TEST_DIR))
        print('TEST ASSETS DIR: {}'.format(cls.TEST_ASSETS_DIR))
        print('---------------------------------------------------------------------------')

    @patch('akl.scrapers.kodi.getAddonDir', autospec=True, return_value=FakeFile("/test"))
    @patch('akl.scrapers.settings.getSettingAsFilePath', autospec=True, return_value=FakeFile("/test"))
    @patch('resources.lib.scraper.net.get_URL', side_effect = mocked_google)
    @patch('resources.lib.scraper.net.download_img')
    @patch('resources.lib.scraper.io.FileName.scanFilesInPath', autospec=True)
    @patch('akl.api.client_get_rom')
    def test_scraping_assets_for_game(self, api_rom_mock: MagicMock, scanner_mock, 
        mock_img_downloader, mock_url_downloader, settings_file, addon_dir):    
        # arrange
        settings = ScraperSettings()
        settings.scrape_metadata_policy = constants.SCRAPE_ACTION_NONE
        settings.scrape_assets_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        settings.asset_IDs_to_scrape = [constants.ASSET_BOXFRONT_ID]
                        
        rom_id = random_string(5)
        rom = ROMObj({
            'id': rom_id,
            'scanned_data': { 'file':Test_google_scrapers.TEST_ASSETS_DIR + '\\castlevania.zip'},
            'platform': 'Nintendo NES',
            'assets': {key: '' for key in constants.ROM_ASSET_ID_LIST},
            'asset_paths': {
                constants.ASSET_BOXFRONT_ID: '/fronts/'
            }
        })
        api_rom_mock.return_value = rom
        
        target = ScrapeStrategy(None, 0, settings, GoogleImageSearch(), FakeProgressDialog())

        # act
        actual = target.process_single_rom(rom_id)
                
        # assert
        self.assertTrue(actual) 
        logger.info(actual.get_data_dic()) 
        
        self.assertTrue(actual.entity_data['assets'][constants.ASSET_BOXFRONT_ID], 'No front defined')
        
    # @patch('resources.lib.scraper.net.get_URL', side_effect = mocked_google)
    # @patch('resources.lib.scraper.net.download_img')
    # @patch('akl.api.client_get_rom')
    # def test_scraping_trailer_assets_for_game(self, api_rom_mock: MagicMock, mock_img_downloader, mock_url_downloader):    
    #     # arrange
    #     settings = ScraperSettings()
    #     settings.scrape_metadata_policy = constants.SCRAPE_ACTION_NONE
    #     settings.scrape_assets_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
    #     settings.asset_IDs_to_scrape = [constants.ASSET_BOXFRONT_ID]
                        
    #     rom_id = random_string(5)
    #     rom = ROMObj({
    #         'id': rom_id,
    #         'filename': Test_google_scrapers.TEST_ASSETS_DIR + '\\castlevania.zip',
    #         'platform': 'Nintendo NES'
    #     })
    #     api_rom_mock.return_value = rom
        
    #     target = ScrapeStrategy(None, 0, settings, YouTubeSearch(), FakeProgressDialog())

    #     # act
    #     actual = target.process_single_rom(rom_id)
                
    #     settings = self.get_test_settings()
    #     status_dic = {}
    #     status_dic['status'] = True
    #     target = YouTubeSearch(settings)
        
    #     asset_to_scrape = g_assetFactory.get_asset_info(ASSET_TRAILER_ID)
    #     f = FakeFile('/roms/castlevania.nes')
    #     platform = 'Nintendo NES'

    #     # act
    #     candidates = target.get_candidates('castlevania', f, f, platform, status_dic)
    #     target.set_candidate(f, platform, candidates[0])
    #     actual = target.get_assets(asset_to_scrape, status_dic)
                
    #     # assert
    #     self.assertTrue(actual)     
    #     self.assertEqual(20, len(actual))
    #     for a in actual:        
    #         print('{} URL: {}'.format(a['display_name'].encode('utf-8'), a['url'].encode('utf-8') ))
