import re
import time
import requests
import lxml.html
from datetime import datetime
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz

from mylog import _log
from config import LaPoste_key, dhl_key, chrome_exe # , Ship24_key, PKGE_key

#------------------------------------------------------------------------------
def get_sentence(txt, nb = -1):
    return ''.join(txt.split('.')[:nb])

def get_local_time(date):
    return parse(date).astimezone(get_localzone())

def get_local_now():
    return datetime.now().astimezone(get_localzone())

def get_leaf_cls(cls):
    subs = cls.__subclasses__()
    for sub in subs:
        for leaf in get_leaf_cls(sub):
            yield leaf
    if not subs:
        yield cls

#------------------------------------------------------------------------------
class Couriers:
    def __init__(self, splash):
        self.couriers = dict( (cls.long_name, cls(splash)) for cls in get_leaf_cls(Courier) )

    def get(self, name):
        return self.couriers.get(name)

    def get_names(self):
        return list( self.couriers.keys() )

    def close(self):
        for courier in self.couriers.values():
            courier.close()

#-------------
def get_simple_check(_min, _max):
    return f'^\w{{{_min},{_max}}}$', f'{_min} à {_max} lettres ou chiffres'

class Courier:
    r_arrow = '→'
    product = 'Envoi'
    fromto = ''
    
    request_timeout = 5 # sec
    nb_retry = 0 
    time_between_retry = 5 # sec

    idship_check_pattern, idship_check_msg = get_simple_check(8, 20)

    delivered_words = ('delivered', 'final delivery', 'livré', 'distribué')
    error_words = ('error', 'erreur')

    subs = ((r'\.$', ''),               # remove ending .
            (r' +', ' '),               # remove extra spaces
            (r'^\W', ''),               # remove leading non alphanumeric char
            (r'(\w):(\w)', r'\1: \2'))  # add space after : 

    def __init__(self, splash):
        pass

    def check_idship(self, idship):
        return re.match(self.idship_check_pattern, idship)

    def clean(self, valid_idships, archived_idships): 
        pass

    def close(self): 
        pass

    def get_url_for_browser(self, idship):
        if idship and self.check_idship(idship):
            return self._get_url_for_browser(idship)

    # def _prepare_response(self, idship): 
    #     pass

    def update(self, idship):
        if not self.check_idship(idship):
            _log (f"'{idship}' mal formé : il faut {self.idship_check_msg}", error = True)
        
        else:
            # try:
            #     self._prepare_response(idship)

            # except requests.exceptions.Timeout:
            #     _log (f' Timeout for request preparation to {self.long_name} about {idship}', error = True)
            
            nb_retry = self.nb_retry
            while True:
                ok = False
                try:
                    ok, r = self._get_response(idship)

                except requests.exceptions.Timeout:
                    _log (f'Timeout request to {self.long_name} for {idship}', error = True)

                if ok or nb_retry <= 0:
                    break

                nb_retry -= 1
                time.sleep(self.time_between_retry) 

            events, infos = self._update(r) if ok else ([], {})

            # remove duplicates
            events = set( tuple(evt.items()) for evt in events )
            events = [ dict(evt) for evt in events ]

            # sort by date
            events.sort(key = lambda evt : evt['date'], reverse = True)
            
            # add couriers and check for delivery & errors events
            delivered = infos.get('delivered', False)
            for event in events:
                event['courier'] = self.short_name
                # clean label
                for sub in self.subs:
                    event['label'] = re.sub(sub[0], sub[1], event['label'].strip())
                
                event['delivered'] = event.get('delivered', False) or any(delivered_word in event['label'].lower() for delivered_word in self.delivered_words)
                if event['delivered']:
                    delivered = True

                event['warn'] = event.get('warn', False) or any(error_word in event['label'].lower() for error_word in self.error_words)
                event['status'] = event.get('status', '')

            status_date = infos.get('status_date', events[0]['date'] if events else get_local_now())

            if not (events or infos.get('status_label')):
                ok = False

            status = dict(  date = status_date, 
                            ok_date = status_date if ok else None, 
                            label = infos.get('status_label', events[0]['label'] if events else 'Erreur'), 
                            warn = infos.get('status_warn', False if events else True), 
                            delivered = delivered)

            return dict(ok = ok, 
                        product = infos.get('product', self.product), 
                        idship = idship, 
                        fromto = infos.get('fromto', self.fromto), 
                        status = status, 
                        events = events)

#-----------------------
USE_UC_V2 = True
CREATE_DRIVER_AT_INIT = False
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

if USE_UC_V2:
    import undetected_chromedriver as webdriver
else:
    import undetected_chromedriver._compat as webdriver

import psutil
import threading
import queue

class SeleniumScrapper(Courier):
    driver_timeout = 100 # s
    lock = threading.Lock()
    n_drivers = 1

    experimental_options = dict(
        prefs = {'translate_whitelists': {'de':'fr', 'es':'fr', 'en':'fr', 'und':'fr', 'zh-CN':'fr', 'zh-TW':'fr'},
                 'translate': {'enabled':'true'},
                 'profile.managed_default_content_settings.images': 2,  # remove image
                 'profile.managed_default_content_settings.cookies': 2, # remove cookies
        },
        excludeSwitches = ['enable-logging']
    )

    options = ( '--no-first-run', 
                '--no-service-autorun', 
                '--password-store=basic', 
                '--lang=fr', 
    )

    options_V1 = ('--window-size=1024,768', ) # reach sliders
    options_V2 = ('--excludeSwitches --enable-logging', 
                  '--blink-settings=imagesEnabled=false')

    def __init__(self, splash):
        self.drivers = queue.Queue() if self.n_drivers > 0 else None
        self.n_created_drivers = 0

        if CREATE_DRIVER_AT_INIT:
            for i in range(self.n_drivers):
                splash.update(f'création pilote {i + 1}/{self.n_drivers}')
                self.create_driver_if_needed()

    def create_driver_if_needed(self):
        with self.lock: # prevents driver creation when it's already being created in another thread
            if self.n_created_drivers < self.n_drivers:

                _log ('Create a DRIVER')
                options = webdriver.ChromeOptions()
                options.headless = True
                options.binary_location = chrome_exe
                
                for option in self.options + (self.options_V2 if USE_UC_V2 else self.options_V1):
                    options.add_argument(option)
                
                if not USE_UC_V2: # prefs do not work on UC v2
                    for k, v in self.experimental_options.items():
                        options.add_experimental_option(k, v)

                driver = webdriver.Chrome(options = options) 
                driver.set_page_load_timeout(self.driver_timeout)

                self.drivers.put(driver)
                self.n_created_drivers += 1
                _log (f'DRIVER #{self.n_created_drivers} created')

    def _get_response(self, idship):
        try:
            self.create_driver_if_needed()
            driver = self.drivers.get()

            _log(f'scrapper load {idship}')
            with self.lock: # do not get all url @ the same time
                driver.get(self._get_url_for_browser(idship))
                
            events = self._scrape(driver, idship)
            return True, events
        
        except (WebDriverException, TimeoutException) as e:
            _log (f'scrapper failure {type(e).__name__} for {idship}', error = True)
            return False, None

        finally:
            self.drivers.put(driver)

    def close(self):
        for proc in psutil.process_iter():
            if 'chromedriver.exe' in proc.name().lower():
                _log (f'kill {proc.name()} {proc.pid}')
                proc.kill()

#-------------------------------
class Cainiao(SeleniumScrapper):
    short_name = 'cn'
    long_name = 'Cainiao'
    fromto = f'CN{Courier.r_arrow}FR'

    timeout_elt = 30 # s

    def _get_url_for_browser(self, idship):
        return f'https://global.cainiao.com/detail.htm?mailNoList={idship}&lang=zh'

    def _scrape(self, driver, idship):
        def get_timeline():
            return driver.find_elements(By.XPATH, '//ol[@class="waybill-path"]/li/p')

        try:
            timeline = get_timeline()
        
        except NoSuchElementException:
            timeline = None

        if not timeline:
            _log(f'scrapper wait slider {idship}')
            slider_locator = (By.XPATH, '//span[@class="nc_iconfont btn_slide"]')
            slider = WebDriverWait(driver, self.timeout_elt).until(EC.element_to_be_clickable(slider_locator))

            slide = driver.find_element(By.XPATH, '//div[@class="scale_text slidetounlock"]/span')
            action = ActionChains(driver)
            action.drag_and_drop_by_offset(slider, slide.size['width'], 0).perform()

            _log(f'scrapper wait datas {idship}')
            data_locator = (By.XPATH, f'//p[@class="waybill-num"][contains(text(),"{idship}")]')
            WebDriverWait(driver, self.timeout_elt).until(EC.visibility_of_element_located(data_locator))
            timeline = get_timeline()

        return [ p.text for p in timeline ]
  
    def _update(self, timeline): 
        events = []
       
        pairwise = zip(timeline[::2], timeline[1::2])
        for label, date in pairwise:
            events.append(dict(date = parse(date).replace(tzinfo = pytz.utc), label = label))

        return events, {}

#---------------------------
class Asendia(Courier):
    short_name = 'ase'
    long_name = 'Asendia'
    fromto = f'CN{Courier.r_arrow}FR'

    headers = {'Content-Type': 'application/json', 'Accept-Language': 'fr'}
    url = 'https://tracking.asendia.com/alliot/items/references'

    def _get_url_for_browser(self, idship):
        return f'https://tracking.asendia.com/tracking/{idship}'

    def _get_response(self, idship): 
        r = requests.post(self.url, json = {'criteria':[idship], 'shipped':False}, headers = self.headers, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []
       
        timeline = r.json()[0]['events']
        for event in timeline:
            label = event['translatedLabelBC']
            location = event['location']['name']

            if label and location:
                location = location.replace('Hong Kong', 'HK')
                country = event['location']['countryCode']
                
                if country not in location:
                    location = ', '.join((location, country))

                date = datetime.utcfromtimestamp(event['date']/1000).replace(tzinfo = pytz.utc)

                events.append(dict(date = date, status = location, label = label))

        return events, {}

#----------------------
class MondialRelay(Courier):
    short_name = 'mr'
    long_name = 'Mondial Relay'
    product = 'Colis'
    fromto = f'FR{Courier.r_arrow}FR'

    idship_check_pattern = r'^\d{8}(\d{2})?(\d{2})?\-\d{5}$'
    idship_check_msg = '8, 10 ou 12 chiffres-code postal'

    def _get_url_for_browser(self, idship):
        number, zip_code = idship.split('-')
        return f'https://www.mondialrelay.fr/suivi-de-colis?numeroExpedition={number}&codePostal={zip_code}'

    def _get_response(self, idship): 
        url = self._get_url_for_browser(idship)
        r = requests.get(url, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []
        
        tree = lxml.html.fromstring(r.content)
        event_by_days = tree.xpath('//div[@class="infos-account"]')

        for event_this_day in event_by_days:
            elts = event_this_day.xpath('./div')
            date_text = elts[0].xpath('.//p//text()')[0]
            event_by_hours = elts[1].xpath('./div')

            for event_this_hour in event_by_hours:
                elts = event_this_hour.xpath('./div/p//text()')
                hour_text, label = elts[:2]
                date = datetime.strptime(f'{date_text} {hour_text}', '%d/%m/%Y %H:%M').replace(tzinfo=get_localzone())
                
                events.append(dict(date = date, label = label))

        return events, {}

#------------------
class GLS(Courier):
    short_name = 'gls'
    long_name = 'GLS'

    def _get_url_for_browser(self, idship):
        return 'https://gls-group.eu/FR/fr/suivi-colis?' # how to add tracking number ??

    def _get_response(self, idship): 
        url = f'https://gls-group.eu/app/service/open/rest/FR/fr/rstt001?match={idship}'
        r = requests.get(url, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []
        product = None
        fromto = None

        json = r.json()

        if shipments := json.get('tuStatus'):
            if len(shipments) > 0:
                shipment = shipments[0]
                if infos := shipment.get('infos'):
                    infos = dict( (info['type'], info) for info in infos)
                    if product := infos.get('PRODUCT'):
                        product = product.get('value')

                        if weight := infos.get('WEIGHT'):
                            product += f" {weight.get('value')}"

                if history := shipment.get('history'):
                    countries = []

                    for  event in history:
                        label = event['evtDscr']
                        address = event['address']
                        
                        countries.append(address['countryCode'])
                        events.append(dict(date = datetime.strptime(f"{event['date']} {event['time']}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=get_localzone()), 
                                           status = f"{address['city']}, {address['countryName']}", 
                                           label = label))

                    if len(countries) > 0:
                        fromto = f'{countries[-1]} {Courier.r_arrow}'
                        if len(countries) > 1:
                            fromto += countries[0]

        return events, dict(product = product, fromto = fromto)

#----------------------
class DPD(Courier):
    short_name = 'dpd'
    long_name = 'DPD'

    def _get_url_for_browser(self, idship):
        return f'https://trace.dpd.fr/fr/trace/{idship}'

    def _get_response(self, idship): 
        url = self._get_url_for_browser(idship)
        r = requests.get(url, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []

        tree = lxml.html.fromstring(r.content)

        infos = tree.xpath('//ul[@class="tableInfosAR"]//text()')
        infos = [info for info in infos if (sinfo := info.replace('\n', '').strip()) != '']
        infos = dict((k, v) for k, v in zip(infos[::2], infos[1::2]))
        product = 'Colis' 
        if weight := infos.get('Poids du colis'):
            product += f' {weight}'

        timeline = tree.xpath('//tr[contains(@id, "ligneTableTrace")]')
        for evt in timeline:
            txts = [stxt for txt in evt.xpath('./td//text()') if (stxt := txt.strip()) != '']
            date, hour, label = txts[:3]
            label = label.replace('Predict vous informe : \n', '').strip()
            location = txts[3] if len(txts)==4 else None

            events.append(dict(date = datetime.strptime(f'{date} {hour}', '%d/%m/%Y %H:%M').replace(tzinfo=get_localzone()), 
                               status = location, label = label))

        return events, dict(product = product)

#----------------------
class NLPost(Courier):
    short_name = 'nl'
    long_name = 'NL Post'

    url = 'https://postnl.post/details/'

    def _get_url_for_browser(self, idship):
        return f'https://postnl.post/tracktrace'

    def _get_response(self, idship): 
        r = requests.post(self.url, data = dict(barcodes = idship), timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []

        tree = lxml.html.fromstring(r.content)
        timeline = tree.xpath('//tr[@class="first detail"]') + tree.xpath('//tr[@class="detail"]')
        for event in timeline:
            date, label = event.xpath('./td/text()')[:2]

            events.append(dict(date = datetime.strptime(date.strip(), '%d-%m-%Y %H:%M').replace(tzinfo=get_localzone()), label = label))

        return events, {}

#----------------------
class FourPX(Courier):
    short_name = '4px'
    long_name = '4PX'

    url = 'https://postnl.post/details/'

    def _get_url_for_browser(self, idship):
        return f'http://track.4px.com/query/{idship}?'

    def _get_response(self, idship): 
        url = self.get_url_for_browser(idship)
        r = requests.get(url, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []

        tree = lxml.html.fromstring(r.content)
        timeline = tree.xpath('//div[@class="track-container"]//li')
        for event in timeline:
            date, hour, label = [stxt for txt in event.xpath('.//text()') if (stxt := re.sub(r'[\n\t]', '', txt).strip().replace('\xa0', '')) !='']
            status, label = label.split('/', 1) if '/' in label else ('', label)

            events.append(dict(date = datetime.strptime(f'{date} {hour}', '%Y-%m-%d %H:%M').replace(tzinfo = pytz.utc),
                               status = status.strip(), label = label.strip() ))
            
        return events, {} 

#----------------------
class LaPoste(Courier):
    short_name = 'lp'
    long_name = 'La Poste'

    idship_check_pattern, idship_check_msg = get_simple_check(11, 15)
    headers = {'X-Okapi-Key': LaPoste_key, 'Accept': 'application/json'}

    codes = dict(
        DR1 = ('Déclaratif réceptionné', False),
        PC1 = ('Pris en charge', False),
        PC2 = ('Pris en charge dans le pays d’expédition', False),
        ET1 = ('En cours de traitement', False),
        ET2 = ('En cours de traitement dans le pays d’expédition', False),
        ET3 = ('En cours de traitement dans le pays de destination', False),
        ET4 = ('En cours de traitement dans un pays de transit', False),
        EP1 = ('En attente de présentation', False),
        DO1 = ('Entrée en Douane', False),
        DO2 = ('Sortie  de Douane', False),
        DO3 = ('Retenu en Douane', True),
        PB1 = ('Problème en cours', True),
        PB2 = ('Problème résolu', False),
        MD2 = ('Mis en distribution', False),
        ND1 = ('Non distribuable', True),
        AG1 = ("En attente d'être retiré au guichet", True),
        RE1 = ("Retourné à l'expéditeur", True),
        DI1 = ('Distribué', False),
        DI2 = ("Distribué à l'expéditeur", True)
    )

    def _get_url_for_browser(self, idship):
        return f'https://www.laposte.fr/outils/suivre-vos-envois?code={idship}'

    def _get_response(self, idship): 
        url = f'https://api.laposte.fr/suivi/v2/idships/{idship}?lang=fr_FR'
        r = requests.get(url, headers = self.headers, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []

        json = r.json()
        shipment = json.get('shipment')

        if shipment:
            product = shipment.get('product').capitalize()

            ctx = shipment.get('contextData')
            fromto = f"{ctx['originCountry']}{Courier.r_arrow}{ctx['arrivalCountry']}"
            
            timeline = list(filter(lambda t : t['status'], shipment.get('timeline')))
            status_label = timeline[-1]['shortLabel']
            delivered = False
            
            for event in shipment.get('event', ()):
                code = event['code']
                if code in ('DI1', 'DI2'):
                    delivered = True

                status, warn = self.codes.get(code, '?')
                label = f"{get_sentence(event['label'], 1)}"

                events.append(dict(date = get_local_time(event['date']), status = status, warn = warn, label = label))

            status_warn = events[-1]['warn'] if events else False
            return events, dict(product = product, fromto = fromto, delivered = delivered, status_warn = status_warn, status_label = status_label.replace('.', ''))

        else:
            return_msg = json.get('returnMessage', 'Erreur')
            status_label = get_sentence(return_msg, 1)
            return events, dict(status_warn = True, status_label = status_label.replace('.', ''))

#----------------------
class DHL(Courier):
    short_name = 'dhl'
    long_name = 'DHL'

    idship_check_pattern, idship_check_msg = r'^\d{10}$', f'10 chiffres'
    headers = {'Accept': 'application/json', 'DHL-API-Key': dhl_key }

    def _get_url_for_browser(self, idship):
        return f'https://www.dhl.com/fr-en/home/our-divisions/parcel/private-customers/tracking-parcel.html?tracking-id={idship}'

    def _get_response(self, idship): 
        url = f'https://api-eu.dhl.com/track/shipments?trackingNumber={idship}&requesterCountryCode=FR'
        r = requests.get(url, headers = self.headers, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []

        json = r.json()
        shipments = json.get('shipments')

        if shipments:
            shipment = shipments[0]
            product = f"DHL {shipment['service']}"
            
            for event in shipment['events']:
                events.append(dict(date = get_local_time(event['date']), label = event['description']))

            return events, dict(product = product)

#----------------------
# class Ship24(Courier):
    
#     url = 'https://api.ship24.com/public/v1'
#     api_key = Ship24_key

#     def __init__(self):
#         self.headers = {'Authorization': f'Bearer {self.api_key}',
#                         'Content-Type': 'application/json',
#                         'charset' : 'utf-8' }

#     def request(self, method, url, json = None):
#         r = requests.request(method, self.url + url, headers = self.headers, json = json, timeout = self.request_timeout)
#         errors = r.json().get('errors')
#         if errors:
#             _log (f'Ship24 error request({url}): {errors}', error = True)
#         return errors is None, r.json()['data']

#     # use to know available couriers code
#     # def show_couriers(self):
#     #     couriers = self.request('GET', '/couriers')['couriers']
#     #     for courier in couriers:
#     #         print (f"FOR {courier['courierName']} USE '{courier['courierCode']}'")

#     def _get_response(self, idship): 
#         json = dict(trackingNumber = idship, courierCode = self.courier)
#         return self.request('POST', f'/trackers/track', json = json)

#     def _update(self, r): 
#         events = []
#         delivered = False

#         trackings = r['trackings'][0]
#         timeline = [evt for evt in trackings['events'] if evt['courierCode'] == self.courier]

#         for event in timeline:
#             event_date = get_local_time(event['datetime'])  # event['utcOffset'] ???
#             event_status = event['location'].replace(self.long_name, '')
#             event_label = event['status']
#             events.append(dict( date = event_date, 
#                                 status = event_status, 
#                                 warn = False, 
#                                 label = event_label))

#             if 'delivered' in event_label.lower():
#                 delivered = True

#         shipment = trackings.get('shipment')
#         fromto = f"{shipment['originCountryCode']}{Courier.r_arrow}{shipment['destinationCountryCode']}"
        
#         return events, dict(fromto = fromto, delivered = delivered)

#----------------------
# class Asendia(Ship24):
#     short_name = 'as'
#     long_name = 'Asendia'
#     courier = 'asendia'

#     def _get_url_for_browser(self, idship):
#         return f'https://tracking.asendia.com/tracking/{idship}'

#-------------------
# import traceback 
# import threading
# from html import unescape
# from datetime import timedelta 

# class PKGE(Courier):
    
#     too_old_archived = 30 # days
#     time_between_update = 5 #hours
#     nb_retry = 2

#     url = 'https://api.pkge.net/v1'
#     api_key = PKGE_key

#     status = dict((
#         (0, ("Suivi en attente de mise à jour", True)),
#         (1, ('Mise à jour du suivi en cours', True)),
#         (2,	("Pas d'information de suivi disponible", True)),
#         (3,	('Colis en transit', False)),
#         (4,	('Colis arrivé à son point de retrait', False)),
#         (5,	('Colis livré', False)),
#         (6,	('Colis non livré', True)),
#         (7,	('Erreur de livraison', True)),
#         (8,	('Colis en préparation pour envoi', True)),
#         (9,	('Fin de suivi du colis', False)),
#     ))

#     def __init__(self):
#         self.headers = {'X-Api-Key': self.api_key, 'Accept-Language' : 'fr'}

#         self.lock = threading.Lock()
#         self.courier_ids = None
#         self.existing = None

#         self.init_courier_ids()
#         self.init_existing()

#     def request(self, method, url):
#         r = requests.request(method, self.url + url, headers = self.headers, timeout = self.request_timeout)
#         code = r.json()['code']
#         if code != 200:
#             _log (f"PKGE error {code} request({url}): {r.json()['payload']}", error = True)
#             return None

#         return r.json()['payload']

#     def init_courier_ids(self):
#         if self.lock.acquire(blocking=False):
#             _log('PKGE init courier_id')
#             try:
#                 couriers = self.request('GET', '/couriers/enabled')
#                 if couriers:
#                     couriers_ids = dict((c['name'], c['id']) for c in couriers)
#                     self.courier_ids = [couriers_ids.get(courier) for courier in self.couriers]
#                     if not self.courier_ids:
#                         _log (f'PKGE !!!!!!! add courier {self.courier} on https://business.pkge.net/docs/packages/add', error = True)
#             except:
#                 _log (traceback.format_exc(), error = True)
#             finally:
#                 self.lock.release()

#     def check_courier_ids(self):
#         if not self.courier_ids:
#             self.init_courier_ids()

#     def init_existing(self):
#         if self.lock.acquire(blocking=False):
#             _log('PKGE init existing')
#             try:
#                 trackings = self.request('GET', '/packages/list')
#                 if trackings:
#                     self.existing = dict( (t['track_number'], t) for t in trackings )
#             except:
#                 _log (traceback.format_exc(), error = True)
#             finally:
#                 self.lock.release()
   
#     def reinit_existing(self):
#         if self.lock.acquire():
#             self.existing = None
#             self.lock.release()

#     def check_existing(self):
#         if not self.existing:
#             self.init_existing()

#     def ask_update(self, idship):
#         _log (f'PKGE update {idship}')
#         self.request('POST', f'/packages/update?trackNumber={idship}')
#         self.reinit_existing()

#     def add(self, idship):
#         self.check_courier_ids()

#         if self.courier_ids:
#             _log (f'PKGE add {idship}')
#             self.request('POST', f'/packages?trackNumber={idship}&courierId={self.courier_ids[0]}')
#             self.reinit_existing()
#             self.init_existing()

#     def delete(self, idship):
#         self.check_courier_ids()
#         self.check_existing()

#         if set(self.courier_ids or ()) & set(self.get_existing(idship, 'couriers_ids')):
#         # if self.courier_id and self.courier_id in self.get_existing(idship, 'couriers_ids'):
#             _log (f'PKGE delete {idship}')
#             self.request('DELETE', f'/packages?trackNumber={idship}')

#     def get_existing(self, idship, attr):
#         return self.existing.get(idship, {}).get(attr)


#     def _prepare_response(self, idship): 
#         self.check_existing()

#         if self.existing:
#             if idship not in self.existing.keys():
#                 self.add(idship)
            
#             # elif not (set(self.courier_ids or ()) & set(self.get_existing(idship, 'couriers_ids'))):
#             #     self.add(idship)

#             last_update = self.get_existing(idship, 'last_tracking_date')
#             if not last_update or get_local_now() - get_local_time(last_update) > timedelta(hours = self.time_between_update):
#                 self.ask_update(idship)

#     def _get_response(self, idship): 
#             r = self.request('GET', f'/packages?trackNumber={idship}')
#             ok = not (r is None or r=='Package not found' or r['updating'] or r['status'] in (0, 1, 2))
#             return ok, r

#     def _update(self, r): 
#         events = []

#         timeline = r['checkpoints']

#         for event in timeline:
#             if event['courier_id'] in self.courier_ids:
#                 event_date = get_local_time(event['date'])
#                 event_label = f"{get_sentence(unescape(event['title']), 1)}"
#                 events.append(dict( date = event_date, 
#                                     status = '', 
#                                     warn = 'error' in event_label.lower() or 'erreur' in event_label.lower(), 
#                                     label = event_label))

#         info_status = r['status']
#         status_label, status_warn = self.status[info_status]
#         delivered = info_status==5
#         status_date = get_local_time(r['last_status_date'])

#         return events, dict(delivered = delivered, status_label = status_label, status_warn = status_warn, status_date = status_date)

#     def clean(self, valid_idships, archived_idships):
#         self.check_existing()

#         if self.existing:
#             # delete trackings that no longer exists
#             for idship in set(self.existing.keys()) - set(valid_idships):
#                 self.delete(idship)
        
#             # delete archived trackings that have'nt been updated since too_old_archived
#             for idship in set(archived_idships):
#                 last_tracking_date = self.get_existing(idship, 'last_tracking_date')
#                 if last_tracking_date:
#                     elapsed = get_local_now() - get_local_time(last_tracking_date)
#                     if elapsed.days > self.too_old_archived:
#                         self.delete(idship)

# #-------------------
# class Cainiao(PKGE):
#     short_name = 'cn'
#     long_name = 'Cainiao'
#     couriers = ('Aliexpress Standard Shipping', 'Aliexpress', 'Global Cainiao')

#     fromto = f'CN{Courier.r_arrow}FR'

#     def _get_url_for_browser(self, idship):
#         return f'https://global.cainiao.com/detail.htm?mailNoList={idship}'
