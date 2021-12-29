import re
import traceback # !!!!!!
import threading# !!!!!!
import time
import requests
import lxml.html
from html import unescape
from datetime import datetime, timedelta # !!!!!!
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz

import os
import random
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from subprocess import CREATE_NO_WINDOW
from fake_useragent import UserAgent

from mylog import _log
from config import PKGE_key, LaPoste_key, Ship24_key, chrome_location

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
    def __init__(self):
        self.couriers = dict( (cls.long_name, cls()) for cls in get_leaf_cls(Courier) )

    def get(self, name):
        return self.couriers.get(name)

    def get_names(self):
        return list( self.couriers.keys() )

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

    idship_check_pattern, idship_check_msg = get_simple_check(8,20)

    def check_idship(self, idship):
        return re.match(self.idship_check_pattern, idship)

    def clean(self, valid_idships, archived_idships):
        pass

    def get_url_for_browser(self, idship):
        if idship and self.check_idship(idship):
            return self._get_url_for_browser(idship)

    def _prepare_response(self, idship): 
        pass

    def update(self, idship):
        if not self.check_idship(idship):
            _log (f"'{idship}' mal formé : il faut {self.idship_check_msg}", error = True)
        
        else:
            try:
                self._prepare_response(idship)

            except requests.exceptions.Timeout:
                _log (f' Timeout for request preparation to {self.long_name} about {idship}', error = True)
            
            nb_retry = self.nb_retry
            while True:
                try:
                    ok, r = self._get_response(idship)

                except requests.exceptions.Timeout:
                    _log (f' Timeout for request to {self.long_name} about {idship}', error = True)

                if ok or nb_retry <= 0:
                    break

                nb_retry -= 1
                time.sleep(self.time_between_retry) 

            events, infos = self._update(r) if ok else ([], {})

            status_date = infos.get('status_date', events[0]['date'] if events else get_local_now())

            status = dict(  date = status_date, 
                            ok_date = status_date if ok else None, 
                            label = infos.get('status_label', events[0]['label'] if events else 'Erreur'), 
                            warn = infos.get('status_warn', False if events else True), 
                            delivered = infos.get('delivered', False))

            return dict(ok = ok, 
                        product = infos.get('product', self.product), 
                        idship = idship, 
                        fromto = infos.get('fromto', self.fromto), 
                        status = status, 
                        events = events)

#-------------------
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
#                 event_label = re.sub(r'^\W', '', event_label) # remove non words character at the beginning
#                 events.append(dict( courier = self.short_name, 
#                                     date = event_date, 
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


#-----------------------
# import undetected_chromedriver as uc

class SeleniumScrapper(Courier):

    driver_timeout = 20 # s
    proxy_timeout = 3000 # ms
    proxys = []
    lock = threading.Lock()

    def __init__(self):
        if not self.proxys:
            self.init_proxys()

    def init_proxys(self):
        self.proxys = []
        url = 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout={self.proxy_timeout}&country=fr&ssl=yes&anonymity=all'
        r = requests.get(url)
        if r.status_code == 200:
            for proxy in r.text.split('\r\n'):
                if proxy:
                    self.proxys.append( dict(ip=proxy, ua=UserAgent().random) )

        _log (f'FOUND {len(self.proxys)} proxys')
        random.shuffle(self.proxys)
        self.index = 0

    def get_working_proxy(self):
        with self.lock:
            while len(self.proxys) > 0:
                index = self.index % len(self.proxys)
                proxy = self.proxys[index]
                
                if proxy.get('tested'):
                    self.index += 1
                    return proxy
                
                else:
                    ip = proxy['ip']
                    _log (f'{ip} CHECK...')

                    try:
                        test = requests.get('https://example.com', timeout = self.proxy_timeout/1000, proxies = dict(http = f'http://{ip}'))
                        # test = requests.get('https://example.com', timeout = self.proxy_timeout/1000, proxies = dict(https = f'https://{ip}', http = f'http://{ip}'))
                        if test.status_code == 200:
                            proxy['tested'] = True
                            _log (f'{ip} OK')
                            self.index += 1
                            return proxy

                    except:
                        pass
                    
                    del self.proxys[index]
                    _log (f'{ip} Removed, {len(self.proxys)} left', error = True)

                    if len(self.proxys) == 0:
                        self.init_proxys()

            _log ('No Proxy left', error = True)

    def remove_proxy(self, proxy):
        with self.lock:
            if proxy in self.proxys:
                self.proxys.remove(proxy)
                _log (f"{proxy['ip']} Removed, {len(self.proxys)} left", error = True)


    def get_page(self, idship):
        options = Options()
        options.headless = True
        options.add_argument("--incognito")
        options.add_argument('--disable-blink-features')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        
        proxy = self.get_working_proxy()
        if proxy:
            ip, ua = proxy['ip'], proxy['ua']
            options.add_argument(f'user-agent={ua}')
            options.add_argument(f'--proxy-server={ip}')
            # options.add_argument('--ignore-certificate-errors')
            _log (f'driver for {idship}, use IP: {ip}')
        
        else:
            _log (f'driver for {idship}, no Proxy')

        path = os.path.dirname(os.path.realpath(__file__))
        driver_path = os.path.join(path, 'chromedriver2.exe')
        service = Service(driver_path)
        service.creationflags = CREATE_NO_WINDOW

        driver = webdriver.Chrome(service = service, options=options)
        driver.set_page_load_timeout(self.driver_timeout)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source":
                "const newProto = navigator.__proto__;"
                "delete newProto.webdriver;"
                "navigator.__proto__ = newProto;"
        })

        # options = uc.ChromeOptions()
        # options.headless = True
        # options.binary_location = chrome_location
        # driver = uc.Chrome(options = options)
        # driver.set_page_load_timeout(self.driver_timeout)

        url = self._get_url_for_browser(idship)
        try:
            driver.get(url)
            title, source = driver.title, driver.page_source
        
        except (WebDriverException, TimeoutException) as e:
            _log (f'proxy failure {type(e).__name__} for {idship}', error = True)
            title, source = None, None
            self.remove_proxy(proxy)

        driver.close()
        # driver.quit()

        return title, source

#-------------------------------
class Cainiao(SeleniumScrapper):
    short_name = 'cn'
    long_name = 'Cainiao'
    fromto = f'CN{Courier.r_arrow}FR'

    nb_retry = 0 

    def _get_url_for_browser(self, idship):
        return f'https://global.cainiao.com/detail.htm?mailNoList={idship}&lang=fr&'

    def _get_response(self, idship): 
        title, page = self.get_page(idship)

        ok = title and page and 'Global Parcel Tracking' in title
        if title and not ok:
            _log (f'selenium opened wrong page "{title}" for {idship}', error = True) 
        return ok, page

    def _update(self, page): 
        events = []
        delivered = False
       
        try:
            tree = lxml.html.fromstring(page)
            timeline = tree.xpath('//ol[@class="waybill-path"]/li')

            for event in timeline:
                label, date = event.xpath('./p/text()')
                events.append(dict( courier = self.short_name, 
                                    date = get_local_time(date), 
                                    status = '', 
                                    warn = 'error' in label.lower(), 
                                    label = label))

                if 'delivered' in label.lower():
                    delivered = True

        except NoSuchElementException:
            _log (traceback.format_exc(), error = True)

        return events, dict(delivered = delivered)

#---------------------------
class Asendia(Courier):
    short_name = 'as'
    long_name = 'Asendia'
    fromto = f'CN{Courier.r_arrow}FR'

    headers = { 'Content-Type': 'application/json',
                'Accept-Language': 'fr'}

    url = 'https://tracking.asendia.com/alliot/items/references'

    def _get_url_for_browser(self, idship):
        return f'https://tracking.asendia.com/tracking/{idship}'

    def _get_response(self, idship): 
        r = requests.post(self.url, json = {'criteria':[idship], 'shipped':False}, headers = self.headers, timeout = self.request_timeout)
        return r.status_code == 200, r

    def _update(self, r): 
        events = []
        delivered = False
       
        timeline = r.json()[0]['events']
        for event in timeline:
            label = event['translatedLabelBC']
            location = event['location']['name']

            if label and location:
                location = location.replace('Hong Kong', 'HK')
                country = event['location']['countryCode']
                
                if country not in location:
                    location = ', '.join((location, country))

                if 'Livré' in label:
                    delivered = True

                date = datetime.utcfromtimestamp(event['date']/1000).replace(tzinfo=pytz.utc)
                # date = datetime.utcfromtimestamp(event['date']/1000).astimezone(get_localzone()) # crash !!!

                events.append(dict( courier = self.short_name, 
                                    date = date, 
                                    status = location, 
                                    warn = False, 
                                    label = label))

        events = set( tuple(evt.items()) for evt in events )
        events = [ dict(evt) for evt in events ]
        events.sort(key = lambda evt : evt['date'], reverse = True)

        return events, dict(delivered = delivered)

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
        delivered = False
        
        tree = lxml.html.fromstring(r.content)
        event_by_days = tree.xpath('//div[@class="infos-account"]')

        for event_this_day in event_by_days:
            elts = event_this_day.xpath('./div')
            date_text = elts[0].xpath('.//p//text()')[0]
            event_by_hours = elts[1].xpath('./div')

            for event_this_hour in event_by_hours:
                elts = event_this_hour.xpath('./div/p//text()')
                hour_text = elts[0]
                label = elts[1].replace('.', '')
                
                date = datetime.strptime(f'{date_text} {hour_text}', '%d/%m/%Y %H:%M').astimezone(get_localzone())
                
                if 'livré' in label:
                    delivered = True

                events.append(dict( courier = self.short_name, 
                                    date = date, 
                                    status = '', 
                                    warn = False, 
                                    label = label))

        return events, dict(delivered = delivered)

#----------------------
class LaPoste(Courier):

    short_name = 'lp'
    long_name = 'La Poste'
    api_key = LaPoste_key

    idship_check_pattern, idship_check_msg = get_simple_check(11,15)

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
    
    products = {'Courrier international' : 'Courrier Int.'}

    def __init__(self):
        self.headers = {'X-Okapi-Key': self.api_key, 'Accept': 'application/json'}

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
            product = shipment.get('product')
            product = self.products.get(product, product).capitalize()

            ctx = shipment.get('contextData')
            fromto = f"{ctx['originCountry']}{Courier.r_arrow}{ctx['arrivalCountry']}"
            
            timeline = list(filter(lambda t : t['status'], shipment.get('timeline')))
            status_label = timeline[-1]['shortLabel']
            delivered = False
            
            for event in shipment.get('event', ()):
                code = event['code']
                if code in ('DI1', 'DI2'):
                    delivered = True

                event_date = get_local_time(event['date'])
                event_status, event_warn = self.codes.get(code, '?')
                event_label = f"{get_sentence(event['label'], 1)}"

                events.append(dict( courier = self.short_name, 
                                    date = event_date, 
                                    status = event_status, 
                                    warn = event_warn or 'erreur' in event_label.lower(), 
                                    label = event_label))

            status_warn = events[-1]['warn'] if events else False
            return events, dict(product = product, fromto = fromto, delivered = delivered, status_warn = status_warn, status_label = status_label.replace('.', ''))

        else:
            return_msg = json.get('returnMessage', 'Erreur')
            status_label = get_sentence(return_msg, 1)
            return events, dict(status_warn = True, status_label = status_label.replace('.', ''))

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
#             event_status = re.sub(' +', ' ', event['location'].replace(self.long_name, '').strip())
#             event_label = re.sub(' +', ' ', event['status'])
#             events.append(dict( courier = self.short_name, 
#                                 date = event_date, 
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
