import re
import time
import requests
import lxml.html
from datetime import datetime
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import urllib3

from mylog import _log
from drivers import Drivers
from config import LaPoste_key, dhl_key 
from local_txts import *

#------------------------------------------------------------------------------
def get_sentence(txt, nb = -1):
    return ''.join(re.split(r'[.!]', txt)[:nb])

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
        self.couriers = {cls.long_name: cls(splash) for cls in get_leaf_cls(Courier)}

    def get(self, name):
        return self.couriers.get(name)

    def get_names(self):
        return list( self.couriers.keys() )

    def close(self):
        for courier in self.couriers.values():
            courier.close()

#-------------
def get_simple_check(_min, _max):
    return f'^\w{{{_min},{_max}}}$', f'{From_txt} {_min} {To_txt} {_max} {Letters_txt} {Or_txt} {Digits_txt}'

class Courier:
    r_arrow = '→'
    product = Default_product_txt
    fromto = ''
    
    request_timeout = 5 # sec
    nb_retry = 0 
    time_between_retry = 5 # sec

    idship_check_pattern, idship_check_msg = get_simple_check(8, 20)

    delivered_matchs = (r'delivered', r'final delivery', r'(?<!être )livré', r'(?<!être )distribué')
    error_words = ('error', 'erreur')

    subs = ((r'\.$', ''),               # remove ending .
            (r' +', ' '),               # remove extra spaces
            (r'^\W', ''),               # remove leading non alphanumeric char
            (r'(\w):(\w)', r'\1: \2'))  # add space after : 

    def __init__(self, splash):
        pass

    def close(self): 
        pass

    def check_idship(self, idship):
        return re.match(self.idship_check_pattern, idship)

    def get_url_for_browser(self, idship):
        if idship and self.check_idship(idship):
            return self._get_url_for_browser(idship)

    def update(self, idship):
        if not self.check_idship(idship):
            _log (f'Wrong {Idship_txt} {idship} ({self.idship_check_msg})', error = True)
        
        else:
            nb_retry = self.nb_retry
            while True:
                ok = False
                try:
                    ok, r = self._get_response(idship)

                except requests.exceptions.Timeout:
                    _log (f'TIMEOUT request to {self.long_name} for {idship}', error = True)

                if ok or nb_retry <= 0:
                    break

                nb_retry -= 1
                time.sleep(self.time_between_retry) 

            events, infos = self._update(r) if ok else ([], {})

            # remove duplicate events
            # https://stackoverflow.com/questions/9427163/remove-duplicate-dict-in-list-in-python
            events = [ dict(evt_tuple) for evt_tuple in {tuple(evt.items()) for evt in events} ]

            # sort by date
            events.sort(key = lambda evt : evt['date'], reverse = True)
            
            # add couriers and check for delivery & errors events
            delivered = infos.get('delivered', False)
            for event in events:
                event['courier'] = self.long_name
                # clean label
                for sub in self.subs:
                    event['label'] = re.sub(sub[0], sub[1], event['label'].strip())
                
                event['delivered'] = event.get('delivered', False) or any(re.search(match, event['label'].lower()) for match in self.delivered_matchs)
                if event['delivered']:
                    delivered = True

                event['warn'] = event.get('warn', False) or any(error_word in event['label'].lower() for error_word in self.error_words)
                event['status'] = event.get('status', '')

            status_date = infos.get('status_date', events[0]['date'] if events else None) # get_local_now())

            if not (events or infos.get('status_label')):
                ok = False

            status = dict(  date = status_date, 
                            ok_date = status_date if ok else None, 
                            label = infos.get('status_label', events[0]['label'] if events else Status_Error_txt), 
                            warn = infos.get('status_warn', False if events else True), 
                            delivered = delivered)

            return dict(ok = ok, 
                        product = infos.get('product', self.product), 
                        idship = idship, 
                        fromto = infos.get('fromto', self.fromto), 
                        status = status, 
                        events = events)

#-----------------------
class Scrapper(Courier):

    errors_catched = (WebDriverException, TimeoutException, 
                      urllib3.exceptions.ProtocolError, 
                      urllib3.exceptions.NewConnectionError, 
                      urllib3.exceptions.MaxRetryError)

    def __init__(self, splash):
        self.drivers = Drivers(splash)

    def _get_response(self, idship):
        try:
            driver = self.drivers.get()

            if driver:
                _log(f'scrapper LOAD - {idship}')
                driver.get(self._get_url_for_browser(idship))
                    
                events = self._scrape(driver, idship)
                return True, events
        
        except self.errors_catched as e: 
            _log (f'scrapper FAILURE - {type(e).__name__} for {idship}', error = True)
            return False, None

        finally:
            if 'driver' in locals() and driver:
                self.drivers.dispose(driver)

    def close(self):
        self.drivers.close()

#-------------------------------
class Cainiao(Scrapper):
    long_name = 'Cainiao'
    fromto = f'CN{Courier.r_arrow}FR'

    timeout_elt = 30 # s

    def _get_url_for_browser(self, idship):
        return f'https://global.cainiao.com/detail.htm?mailNoList={idship}&lang=zh'

    def get_timeline(self, driver):
        return driver.find_elements(By.XPATH, '//ol[@class="waybill-path"]/li/p')

    def _scrape(self, driver, idship):
        try:
            timeline = self.get_timeline(driver)
        
        except NoSuchElementException:
            timeline = None

        if not timeline:
            _log(f'scrapper WAIT slider - {idship}')
            slider_locator = (By.XPATH, '//span[@class="nc_iconfont btn_slide"]')
            slider = WebDriverWait(driver, self.timeout_elt).until(EC.element_to_be_clickable(slider_locator))

            slide = driver.find_element(By.XPATH, '//div[@class="scale_text slidetounlock"]/span')
            action = ActionChains(driver)
            action.drag_and_drop_by_offset(slider, slide.size['width'], 0).perform()

            _log(f'scrapper WAIT datas - {idship}')
            data_locator = (By.XPATH, f'//p[@class="waybill-num"][contains(text(),"{idship}")]')
            WebDriverWait(driver, self.timeout_elt).until(EC.visibility_of_element_located(data_locator))
            timeline = self.get_timeline(driver)

        return [ p.text for p in timeline ]
  
    def _update(self, timeline): 
        events = []
       
        pairwise = zip(timeline[::2], timeline[1::2])
        for label, date in pairwise:
            events.append(dict(date = parse(date).replace(tzinfo = pytz.utc), label = label))

        return events, {}

#---------------------------
class Asendia(Courier):
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
    long_name = 'Mondial Relay'
    product = 'Colis'
    fromto = f'FR{Courier.r_arrow}FR'

    idship_check_pattern = r'^\d{8}(\d{2})?(\d{2})?\-\d{5}$'
    idship_check_msg = f'8, 10 {Or_txt} 12 {Digits_txt}-{Zipcode_txt}'

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
                event_delivered = code in ('DI1', 'DI2')
                delivered |= event_delivered

                status, warn = self.codes.get(code, '?')
                label = f"{get_sentence(event['label'], 1)}"

                events.append(dict(date = get_local_time(event['date']), status = status, warn = warn, label = label, delivered = event_delivered))

            status_warn = events[-1]['warn'] if events else False
            return events, dict(product = product, fromto = fromto, delivered = delivered, status_warn = status_warn, status_label = status_label.replace('.', ''))

        else:
            return_msg = json.get('returnMessage', 'Erreur')
            status_label = get_sentence(return_msg, 1)
            return events, dict(status_warn = True, status_label = status_label.replace('.', ''))

#----------------------
class DHL(Courier):
    long_name = 'DHL'

    idship_check_pattern, idship_check_msg = r'^\d{10}$', f'10 {Letters_txt}'
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
