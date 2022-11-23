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

    mocked_json = ''
    if 'https://customsearch.googleapis.com/customsearch/v1' in url:
        mocked_json = os.path.abspath(os.path.join(Test_google_scrapers.TEST_ASSETS_DIR,'google_result.json'))
    if 'https://youtube.googleapis.com/youtube/v3' in url:
        mocked_json = os.path.abspath(os.path.join(Test_google_scrapers.TEST_ASSETS_DIR,'youtube_result.json'))
    if mocked_json == '':
        return net.get_URL_as_json(url, url)

    print('reading mocked data from file: {}'.format(mocked_json))
    return json.loads(read_file(mocked_json))

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
    @patch('resources.lib.scraper.net.get_URL_as_json', side_effect = mocked_google)
    @patch('resources.lib.scraper.net.download_img')
    @patch('resources.lib.scraper.io.FileName.scanFilesInPath', autospec=True)
    @patch('akl.api.client_get_rom')
    def test_scraping_assets_for_game(self, api_rom_mock: MagicMock, scanner_mock, 
        mock_img_downloader, mock_url_downloader, settings_file, addon_dir):    
        # arrange
        settings = ScraperSettings()
        settings.scrape_metadata_policy = constants.SCRAPE_ACTION_NONE
        settings.scrape_assets_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        settings.asset_selection_mode = constants.SCRAPE_AUTOMATIC
        settings.asset_IDs_to_scrape = [constants.ASSET_BOXFRONT_ID]
                        
        rom_id = random_string(5)
        rom = ROMObj({
            'id': rom_id,
            'm_name': 'castlevania',
            'filename': Test_google_scrapers.TEST_ASSETS_DIR + '\\castlevania.zip',
            'platform': 'Nintendo NES',
            'scanned_data': {
                'identifier': 'castlevania'
            },
            'asset_paths': {
                constants.ASSET_BOXFRONT_ID: '/fronts/'
            },
            'assets': {key: '' for key in constants.ROM_ASSET_ID_LIST}
        })
        api_rom_mock.return_value = rom
        
        scraper = GoogleImageSearch()
        scraper.set_verbose_mode(True)
        target = ScrapeStrategy(None, 0, settings, scraper, FakeProgressDialog())

        # act
        actual = target.process_single_rom(rom_id)
                
        # assert
        self.assertTrue(actual) 
        logger.info(actual.get_data_dic()) 
        
        self.assertTrue(actual.entity_data['assets'][constants.ASSET_BOXFRONT_ID], 'No front defined')
        
    @patch('akl.scrapers.kodi.getAddonDir', autospec=True, return_value=FakeFile("/test"))
    @patch('akl.scrapers.settings.getSettingAsFilePath', autospec=True, return_value=FakeFile("/test"))
    @patch('resources.lib.scraper.net.get_URL_as_json', side_effect = mocked_google)
    @patch('resources.lib.scraper.io.FileName.scanFilesInPath', autospec=True)
    @patch('akl.api.client_get_rom')
    def test_scraping_trailer_assets_for_game(self, api_rom_mock: MagicMock, scanner_mock, 
        mock_img_downloader, settings_file, addon_dir): 
        # arrange
        settings = ScraperSettings()
        settings.scrape_metadata_policy = constants.SCRAPE_ACTION_NONE
        settings.scrape_assets_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        settings.asset_selection_mode = constants.SCRAPE_AUTOMATIC
        settings.asset_IDs_to_scrape = [constants.ASSET_TRAILER_ID]
                        
        rom_id = random_string(5)
        rom = ROMObj({
            'id': rom_id,
            'm_name': 'call of duty ww-ii',
            'filename': Test_google_scrapers.TEST_ASSETS_DIR + '\\codwwii.zip',
            'platform': 'Windows',
            'scanned_data': {
                'identifier': 'codwwii'
            },
            'asset_paths': {
                constants.ASSET_TRAILER_ID: '/trailers/'
            },
            'assets': {key: '' for key in constants.ROM_ASSET_ID_LIST}
        })
        api_rom_mock.return_value = rom
        
        scraper = GoogleImageSearch()
        scraper.set_verbose_mode(True)
        target = ScrapeStrategy(None, 0, settings, scraper, FakeProgressDialog())

        # act
        actual = target.process_single_rom(rom_id)
                
        # assert
        self.assertTrue(actual) 
        logger.info(actual.get_data_dic()) 
        
    def test_cleaning_url(self):    
        # arrange
        target = GoogleImageSearch()
        url = "https://customsearch.googleapis.com/customsearch/v1?cx=ABC&q=test&searchType=image&key=Q9Q9&start=1"
        expected = "https://customsearch.googleapis.com/customsearch/v1?cx=***&q=test&searchType=image&key=***&start=1"
        
        # act
        actual = target._clean_URL_for_log(url)

        # assert
        assert expected == actual