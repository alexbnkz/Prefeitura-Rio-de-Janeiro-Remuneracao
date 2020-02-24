# -*- coding: utf-8 -*-
import os
import csv
import json
import time
import platform
from uuid import uuid4
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By as by
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract as ocr
from concurrent.futures import ThreadPoolExecutor,as_completed

URL = 'http://jeap.rio.rj.gov.br/contrachequeapi/transparencia'
ROOT_DIR = os.path.realpath(os.path.dirname(__file__))

# you can get data from customized search
# or set search = None to get ALL 
search = [
    'Secretaria Municipal de Urbanismo'
]

# get sub agencies
get_child = False

def get_time_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_browser(driver, download_dir = None):
    #  driver = geckodriver or chromedriver

    if 'Linux' in platform.system():
        driver_bin = driver
        bin_path =  os.path.join(ROOT_DIR, driver_bin)
        os.environ['PATH'] = f"{os.getenv('PATH')}:{bin_path}" 
    else:
        driver_bin = f'{driver}.exe'
        bin_path =  os.path.join(ROOT_DIR, driver_bin)
        os.environ['PATH'] = f"{os.getenv('PATH')};{bin_path}"

    browser = None

    if 'geckodriver' in driver:
        # options = FirefoxOptions()
        # options.headless = True

        profile = FirefoxProfile()
        profile.set_preference("browser.download.folderList", 2)

        profile.set_preference(
            "browser.download.manager.showWhenStarting", False)
        profile.set_preference(
            "browser.helperApps.neverAsk.saveToDisk",
                "csv,application/x-csv,text/csv")

        if download_dir:
            profile.set_preference("browser.download.dir", 
                                os.path.join(ROOT_DIR, download_dir))
        else:
            profile.set_preference("browser.download.dir", ROOT_DIR)

        browser = webdriver.Firefox(executable_path=bin_path, 
                                        firefox_profile=profile)
    else:
        # TODO
        # develop chromedriver setting
        # not working at all

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--no-sandbox')
        browser = webdriver.Chrome(executable_path=bin_path, 
                                            options=chrome_options)

    return browser

def call_recursive(browser, node, treenode):
    treenode.append(node)

    root = browser.find_element_by_id(node['id'])
    soup = BeautifulSoup(root.get_attribute('innerHTML'), 
                                        features='html.parser')
    for el in soup.select('li'):
        node_rowkey = f".{el['data-rowkey']}".replace(f".{node['rowkey']}", '')
        if node_rowkey.count('_') == 1:

            ID = el['id']
            ROWKEY = el['data-rowkey']
            NAME = el.select(
                'span.ui-treenode-label.ui-corner-all')[0].text.strip()

            node_child = { 
                'id': ID, 
                'rowkey': ROWKEY, 
                'name': NAME 
            }
            call_recursive(browser, node_child, treenode)

    return treenode

def decode_captcha(browser):
    time.sleep(1)
    css = "div[id='tabView:formFiltroOrgaos:codigoCaptchOrgaoField'] img"

    ImgCaptcha = browser.find_element_by_css_selector(css)
    captcha_id = ImgCaptcha.get_attribute('src').split('captcha?f=')[1]
    IMG_FILE =  os.path.join(ROOT_DIR, 'captcha', f'{captcha_id}.png')
    location = ImgCaptcha.location
    size = ImgCaptcha.size

    browser.save_screenshot(IMG_FILE)
    x = location['x']
    y = location['y']
    width = location['x'] + size['width']
    height = location['y'] + size['height']

    im = Image.open(IMG_FILE)
    im = im.crop((int(x), int(y), int(width), int(height)))
    im.save(IMG_FILE)
    captcha = ocr.image_to_string(im)
    os.remove(IMG_FILE)

    print(f"{get_time_now()} New captcha {captcha} :) ")

    return captcha

#===============================================================================
if __name__ == '__main__':
    print(f"{get_time_now()} Starting... ")

    browser = get_browser('geckodriver')

    try:
        wait = WebDriverWait(browser, 15)
        browser.get(URL)

        bt_query_agency = wait.until(
            ec.presence_of_element_located((by.CSS_SELECTOR,
                            'a[href="#tabView:consultaPorOrgao"]')))
        bt_query_agency.click()

        agencies = []

        # get root
        root = browser.find_element_by_css_selector(
                                    'li.ui-treenode.ui-treenode-parent')
        soup = BeautifulSoup(root.get_attribute('innerHTML'), 
                                            features='html.parser')

        for el in soup.select('li'):
            if el['data-rowkey'].count('_') == 1:

                ID = el['id']
                ROWKEY = el['data-rowkey']
                NAME = el.select(
                    'span.ui-treenode-label.ui-corner-all')[0].text.strip()

                node = { 
                    'id': ID, 
                    'rowkey': ROWKEY, 
                    'name': NAME 
                }

                if get_child:
                    if search:
                        if NAME in search:
                            agencies = call_recursive(browser, node, agencies)
                    else:
                        agencies = call_recursive(browser, node, agencies)
                else:
                    if search:
                        if NAME in search:
                            agencies.append(node)
                    else:
                        agencies.append(node)

    except Exception as e:
        print(f"{get_time_now()} Try again! This error has not handled")
        print(f"{get_time_now()} ERROR {e}")
        browser.quit()
        exit(0)

    code_agency = {}

    # downloading CSV from agencies
    for row in agencies:
        print(f"{get_time_now()} downloading {row['name']} ")

        ## IT IS NOT PERFORMATIC !
        # download_dir = os.path.join(ROOT_DIR, row['rowkey'])
        # if os.path.isfile(download_dir):
        #     os.mkdir(download_dir)
        # browser = get_browser('geckodriver', download_dir)
        # wait = WebDriverWait(browser, 15)
        # browser.get(URL)
        # bt_query_agency = wait.until(
        #     ec.presence_of_element_located((by.CSS_SELECTOR,
        #                     'a[href="#tabView:consultaPorOrgao"]')))
        # bt_query_agency.click()

        css = f"li[id='{row['id']}'] span"
        agency = browser.find_element_by_css_selector(css)
        browser.execute_script("arguments[0].scrollIntoView();", agency)
        browser.execute_script("arguments[0].click();", agency)
        
        time.sleep(5)

        css = f"div[id='tabView:formFiltroOrgaos:j_idt60_content']"
        info = browser.find_element_by_css_selector(css)

        code = info.text.split('\n')[4].strip()

        code_agency[code] = row['name']

        tCap = 'tabView:formFiltroOrgaos:codigoCaptchOrgaoField:txtCaptchaOrgao'
        in_capt = browser.find_element_by_css_selector(f"input[id='{tCap}']")

        # decode_captcha is not perfct
        captcha = decode_captcha(browser)

        browser.execute_script(
            f"arguments[0].value='{captcha}';", in_capt)

        css = "button[id='tabView:formFiltroOrgaos:btnConsultarOrgao']"
        bt_show_employees = browser.find_element_by_css_selector(css)
        bt_show_employees.click()

        time.sleep(8)

        try:
            # some agencies may not have record
            # in the current month/year

            css = "button[id='formResultado:btnExportCsv']"
            bt_csv = browser.find_element_by_css_selector(css)
            browser.execute_script("arguments[0].scrollIntoView();", bt_csv)
            browser.execute_script("arguments[0].click();", bt_csv)

            print(f"{get_time_now()} Wait download finish!")
            time.sleep(5)
        except Exception as e:
            print(f"{get_time_now()} ERROR {e}")
            continue

    try:
        browser.quit()
    except Exception as e:
        pass

    # processing CSV data
    for CSV_FILE in list(filter(lambda x: '.csv' in x, os.listdir(ROOT_DIR))):
        print(f"{get_time_now()} processing {CSV_FILE} ")

        with open(os.path.join(ROOT_DIR, CSV_FILE), 
                encoding='utf-8', errors='ignore') as f:

            reader = csv.reader(f, delimiter=';')
            first = True

            for row in reader:
                if not first:
                    matricula = row[0]
                    nome = row[1]
                    lotacao = row[2]
                    mes_ano = row[3]
                    folha = row[4]
                    vantagens = row[5].strip()
                    descontos = row[6].strip()
                    liquido = row[7].strip()

                    dict_data = {
                        'date_scraping': get_time_now(),
                        'url': URL,
                        'orgao': code_agency[lotacao], 
                        'matricula': matricula, 
                        'nome': nome, 
                        'lotacao': lotacao, 
                        'mes_ano': mes_ano, 
                        'folha': folha, 
                        'vantagens': vantagens, 
                        'descontos': descontos, 
                        'liquido': liquido
                    }
                    
                    # hashing json file name with uuid
                    hash = uuid4().hex.lower()
                    
                    file_json = os.path.join(ROOT_DIR, 'data', f'{hash}.json')

                    # save file 
                    with open(file_json, mode="w") as f:
                        f.write(json.dumps(dict_data, indent=4))

                    print(f'{get_time_now()} [ Ok ] {hash} {nome}')

                else:
                    first = not first

        # I rather remove processed files :D
        os.remove(os.path.join(ROOT_DIR, CSV_FILE))

    exit(0)