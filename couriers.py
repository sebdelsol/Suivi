import re
import traceback
import threading
import time
import requests
import lxml.html
from html import unescape
from datetime import datetime, timedelta
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz
import webbrowser

from mylog import _log
from apiKeys import PKGE_key, LaPoste_key, Ship24_key

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
class Courier:
    r_arrow = '→'
    product = 'Envoi'
    fromto = ''
    request_timeout = 5

    def clean(self, valid_idships, archived_idships):
        pass

    def get_url(self, idship):
        if idship:
            return self.get_link(idship)
    
    def open_in_browser(self, idship):
        url = self.get_url(idship)
        if url :
            webbrowser.open(url)

    def update(self, idship):
        ok, r = self._get_response(idship)
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
class PKGE(Courier):
    
    too_old_archived = 30 # days
    time_between_update = 5 #hours
    request_timeout = 3 # sec
    nb_retry = 2 # sec
    time_between_retry = 5 # sec

    url = 'https://api.pkge.net/v1'
    api_key = PKGE_key

    status = dict((
        (0, ("Suivi en attente de mise à jour", True)),
        (1, ('Mise à jour du suivi en cours', True)),
        (2,	("Pas d'information de suivi disponible", True)),
        (3,	('Colis en transit', False)),
        (4,	('Colis arrivé à son point de retrait', False)),
        (5,	('Colis livré', False)),
        (6,	('Colis non livré', True)),
        (7,	('Erreur de livraison', True)),
        (8,	('Colis en préparation pour envoi', True)),
        (9,	('Fin de suivi du colis', False)),
    ))

    def __init__(self):
        self.headers = {'X-Api-Key': self.api_key, 'Accept-Language' : 'fr'}

        self.lock = threading.Lock()
        self.courier_ids = None
        self.existing = None

        self.init_courier_ids()
        self.init_existing()

    def request(self, method, url):
        r = requests.request(method, self.url + url, headers = self.headers, timeout = self.request_timeout)
        code = r.json()['code']
        if code != 200:
            _log (f"PKGE error {code} request({url}): {r.json()['payload']}")
            return None

        return r.json()['payload']

    def init_courier_ids(self):
        if self.lock.acquire(blocking=False):
            _log('PKGE init courier_id')
            try:
                couriers = self.request('GET', '/couriers/enabled')
                if couriers:
                    couriers_ids = dict((c['name'], c['id']) for c in couriers)
                    self.courier_ids = [couriers_ids.get(courier) for courier in self.couriers]
                    if not self.courier_ids:
                        _log (f'PKGE !!!!!!! add courier {self.courier} on https://business.pkge.net/docs/packages/add')
            except:
                _log (traceback.format_exc(), error = True)
            finally:
                self.lock.release()

    def check_courier_ids(self):
        if not self.courier_ids:
            self.init_courier_ids()

    def init_existing(self):
        if self.lock.acquire(blocking=False):
            _log('PKGE init existing')
            try:
                trackings = self.request('GET', '/packages/list')
                if trackings:
                    self.existing = dict( (t['track_number'], t) for t in trackings )
            except:
                _log (traceback.format_exc(), error = True)
            finally:
                self.lock.release()
   
    def reinit_existing(self):
        if self.lock.acquire():
            self.existing = None
            self.lock.release()

    def check_existing(self):
        if not self.existing:
            self.init_existing()

    def ask_update(self, idship):
        _log (f'PKGE update {idship}')
        self.request('POST', f'/packages/update?trackNumber={idship}')
        self.reinit_existing()

    def add(self, idship):
        self.check_courier_ids()

        if self.courier_ids:
            _log (f'PKGE add {idship}')
            self.request('POST', f'/packages?trackNumber={idship}&courierId={self.courier_ids[0]}')
            self.reinit_existing()
            self.init_existing()

    def delete(self, idship):
        self.check_courier_ids()
        self.check_existing()

        if set(self.courier_ids or ()) & set(self.get_existing(idship, 'couriers_ids')):
        # if self.courier_id and self.courier_id in self.get_existing(idship, 'couriers_ids'):
            _log (f'PKGE delete {idship}')
            self.request('DELETE', f'/packages?trackNumber={idship}')

    def get_existing(self, idship, attr):
        return self.existing.get(idship, {}).get(attr)


    def _get_response(self, idship): 
        self.check_existing()

        if self.existing:
            if idship not in self.existing.keys():
                self.add(idship)
            
            # elif not (set(self.courier_ids or ()) & set(self.get_existing(idship, 'couriers_ids'))):
            #     self.add(idship)

            last_update = self.get_existing(idship, 'last_tracking_date')
            if not last_update or get_local_now() - get_local_time(last_update) > timedelta(hours = self.time_between_update):
                self.ask_update(idship)


        nb_retry = self.nb_retry
        while True:
            r = self.request('GET', f'/packages?trackNumber={idship}')

            ok = not (r is None or r=='Package not found' or r['updating'] or r['status'] in (0, 1, 2))
            if ok or nb_retry <= 0:
                return ok, r
            nb_retry -= 1
            time.sleep(self.time_between_retry) 


    def _update(self, r): 
        events = []

        timeline = r['checkpoints']

        for event in timeline:
            if event['courier_id'] in self.courier_ids:
                event_date = get_local_time(event['date'])
                event_label = f"{get_sentence(unescape(event['title']), 1)}"
                event_label = re.sub(r'^\W', '', event_label) # remove non words character at the beginning
                events.append(dict( courier = self.short_name, 
                                    date = event_date, 
                                    status = '', 
                                    warn = 'error' in event_label.lower() or 'erreur' in event_label.lower(), 
                                    label = event_label))

        info_status = r['status']
        status_label, status_warn = self.status[info_status]
        delivered = info_status==5
        status_date = get_local_time(r['last_status_date'])

        return events, dict(delivered = delivered, status_label = status_label, status_warn = status_warn, status_date = status_date)

    def clean(self, valid_idships, archived_idships):
        self.check_existing()

        if self.existing:
            # delete trackings that no longer exists
            for idship in set(self.existing.keys()) - set(valid_idships):
                self.delete(idship)
        
            # delete archived trackings that have'nt been updated since too_old_archived
            for idship in set(archived_idships):
                last_tracking_date = self.get_existing(idship, 'last_tracking_date')
                if last_tracking_date:
                    elapsed = get_local_now() - get_local_time(last_tracking_date)
                    if elapsed.days > self.too_old_archived:
                        self.delete(idship)

#-------------------
class Cainiao(PKGE):
    short_name = 'cn'
    long_name = 'Cainiao'
    couriers = ('Aliexpress Standard Shipping', 'Aliexpress', 'Global Cainiao')

    fromto = f'CN{Courier.r_arrow}FR'

    def get_link(self, idship):
        return f'https://global.cainiao.com/detail.htm?mailNoList={idship}'


#---------------------------
class Asendia(Courier):
    short_name = 'as'
    long_name = 'Asendia'
    fromto = f'CN{Courier.r_arrow}FR'

    headers = { 'Content-Type': 'application/json',
                'Accept-Language': 'fr'}

    url = 'https://tracking.asendia.com/alliot/items/references'

    def get_link(self, idship):
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

    def get_link(self, idship):
        split = idship.split('-')
        if len(split) == 2:
            number, zip_code = idship.split('-')
            return f'https://www.mondialrelay.fr/suivi-de-colis?numeroExpedition={number}&codePostal={zip_code}'

    def _get_response(self, idship): 
        url = self.get_link(idship)
        if url :
            r = requests.get(url, timeout = self.request_timeout)
            return r.status_code == 200, r
        else:
            _log (f'!!! {self.long_name} needs tracking number-zipcode')
            return False, None

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

    def get_link(self, idship):
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
#             _log (f'Ship24 error request({url}): {errors}')
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

#     def get_link(self, idship):
#         return f'https://tracking.asendia.com/tracking/{idship}'
