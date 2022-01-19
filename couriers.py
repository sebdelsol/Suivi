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

from log import log
from drivers import DriverHandler
from config import LaPoste_key, dhl_key
import localization as TXT


def get_sentence(txt, nb=-1):
    return ''.join(re.split(r'[.!]', txt)[:nb])


def get_local_time(date):
    return parse(date).astimezone(get_localzone())


def get_local_now():
    return datetime.now().astimezone(get_localzone())


def get_all_subclasses(cls):
    all_subclasses = set()

    for subclass in cls.__subclasses__():
        all_subclasses.add(subclass)
        all_subclasses |= get_all_subclasses(subclass)

    return all_subclasses


class Couriers:
    driver_handler = None

    def __init__(self, splash=None):
        self.couriers = {cls.name: cls() for cls in get_all_subclasses(Courier)}
        log(f"Init Couriers {', '.join(self.couriers.keys())}")

        # create and set a driver_handler if needed
        if in_need := [courier for courier in self.couriers.values() if hasattr(courier, 'set_driver_handler')]:
            self.driver_handler = DriverHandler(splash)
            for courier in in_need:
                courier.set_driver_handler(self.driver_handler)

    def get(self, name):
        return self.couriers.get(name)

    def get_names(self):
        return list(self.couriers.keys())

    def close(self):
        if self.driver_handler:
            self.driver_handler.close()


def get_simple_validation(_min, _max):
    return fr'^\w{{{_min},{_max}}}$', f'{TXT.from_} {_min} {TXT.to_} {_max} {TXT.letters} {TXT.or_} {TXT.digits}'


class Courier:
    r_arrow = '→'
    product = TXT.default_product
    fromto = ''

    request_timeout = 5  # sec
    nb_retry = 0
    time_between_retry = 5  # sec

    idship_validation, idship_validation_msg = get_simple_validation(8, 20)

    delivered_searchs = (r'(?<!be )delivered', r'final delivery', r'(?<!être )livré', r'(?<!être )distribué', r'mis à disposition')
    error_words = ('error', 'erreur')

    subs = ((r'\.$', ''),               # remove ending .
            (r' +', ' '),               # remove extra spaces
            (r'^\W', ''),               # remove leading non alphanumeric char
            (r'(\w):(\w)', r'\1: \2'))  # add space after :

    def __init__(self):
        self.idship_validation = re.compile(self.idship_validation).match
        self.delivered_searchs = [re.compile(pattern).search for pattern in self.delivered_searchs]

    def log(self, *args, **kwargs):
        args = list(args)
        args[0] = f'{args[0]}, {self.name}'
        log(*args, **kwargs)

    def validate_idship(self, idship):
        return self.idship_validation(idship)

    def get_valid_url_for_browser(self, idship):
        if idship and self.validate_idship(idship):
            return self.get_url_for_browser(idship)

    def update(self, idship):
        if not self.validate_idship(idship):
            self.log(f'Wrong {TXT.idship} {idship} ({self.idship_validation_msg})', error=True)

        else:
            nb_retry = self.nb_retry
            while True:
                try:
                    content = self.get_content(idship)

                except requests.exceptions.Timeout:
                    self.log(f'TIMEOUT request to {self.name} for {idship}', error=True)
                    content = None

                if nb_retry <= 0 or content is not None:
                    break

                nb_retry -= 1
                time.sleep(self.time_between_retry)

            ok = True if content is not None else False
            events, infos = self.parse_content(content) if ok else ([], {})

            # remove duplicate events
            # https://stackoverflow.com/questions/9427163/remove-duplicate-dict-in-list-in-python
            events = [dict(evt_tuple) for evt_tuple in {tuple(evt.items()) for evt in events}]

            # sort by date
            events.sort(key=lambda evt: evt['date'], reverse=True)

            # add couriers and check for delivery & errors events
            delivered = infos.get('delivered', False)
            for event in events:
                event['courier'] = self.name
                # clean label
                for sub in self.subs:
                    event['label'] = re.sub(sub[0], sub[1], event['label'].strip())

                event['delivered'] = event.get('delivered', False) or any(search(event['label'].lower()) for search in self.delivered_searchs)
                if event['delivered']:
                    delivered = True

                event['warn'] = event.get('warn', False) or any(error_word in event['label'].lower() for error_word in self.error_words)
                event['status'] = event.get('status', '')

            status_date = infos.get('status_date', events[0]['date'] if events else None)

            if not (events or infos.get('status_label')):
                ok = False

            status = dict(date=status_date,
                          ok_date=status_date if ok else None,
                          label=infos.get('status_label', events[0]['label'] if events else TXT.status_error),
                          warn=infos.get('status_warn', False if events else True),
                          delivered=delivered)

            return dict(ok=ok,
                        product=infos.get('product', self.product),
                        idship=idship,
                        fromto=infos.get('fromto', self.fromto),
                        status=status,
                        events=events)


# class decorator
def Scrapper(timeout=30):
    def decorator(courier):
        errors_catched = (WebDriverException, TimeoutException,
                          urllib3.exceptions.ProtocolError,
                          urllib3.exceptions.NewConnectionError,
                          urllib3.exceptions.MaxRetryError)

        def set_driver_handler(self, driver_handler):
            self.driver_handler = driver_handler

        def wrapped_get_content(self, idship):
            try:
                driver = self.driver_handler.get()

                if driver:
                    self.log(f'scrapper LOAD - {idship}')
                    url = self.get_url_for_browser(idship)
                    if url:
                        driver.get(url)
                        return self.inner_get_content(driver, idship)

                    else:
                        error = "can't find url"

                else:
                    error = 'no driver available'

            except errors_catched as e:
                error = type(e).__name__

            finally:
                if 'driver' in locals() and driver:
                    self.driver_handler.dispose(driver)

            self.log(f'scrapper FAILURE - {error} for {idship}', error=True)

        courier.timeout_elt = timeout  # s
        courier.inner_get_content = courier.get_content
        courier.get_content = wrapped_get_content
        courier.set_driver_handler = set_driver_handler
        return courier

    return decorator


@Scrapper(timeout=30)
class Cainiao(Courier):
    name = 'Cainiao'
    fromto = f'CN{Courier.r_arrow}FR'

    def get_url_for_browser(self, idship):
        return f'https://global.cainiao.com/detail.htm?mailNoList={idship}&lang=zh'

    #  do not return any selenium objects, the driver is disposed after
    def get_content(self, driver, idship):
        data_locator = (By.XPATH, f'//p[@class="waybill-num"][contains(text(),"{idship}")]')

        try:
            is_data = driver.find_elements(*data_locator)

        except NoSuchElementException:
            is_data = None

        if not is_data:
            self.log(f'scrapper WAIT slider - {idship}')
            slider_locator = (By.XPATH, '//span[@class="nc_iconfont btn_slide"]')
            slider = WebDriverWait(driver, self.timeout_elt).until(EC.element_to_be_clickable(slider_locator))

            slide = driver.find_element(By.XPATH, '//div[@class="scale_text slidetounlock"]/span')
            action = ActionChains(driver)
            action.drag_and_drop_by_offset(slider, slide.size['width'], 0).perform()

            self.log(f'scrapper WAIT datas - {idship}')
            data_locator = (By.XPATH, f'//p[@class="waybill-num"][contains(text(),"{idship}")]')
            WebDriverWait(driver, self.timeout_elt).until(EC.visibility_of_element_located(data_locator))

        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, tree):
        events = []

        timeline = tree.xpath('//ol[@class="waybill-path"]/li')
        for li in timeline:
            txts = li.xpath('./p/text()')
            label, date = txts[:2]
            events.append(dict(date=parse(date).replace(tzinfo=pytz.utc), label=label))

        return events, {}


class Asendia(Courier):
    name = 'Asendia'
    fromto = f'CN{Courier.r_arrow}FR'

    headers = {'Content-Type': 'application/json', 'Accept-Language': 'fr'}
    url = 'https://tracking.asendia.com/alliot/items/references'

    def get_url_for_browser(self, idship):
        return f'https://tracking.asendia.com/tracking/{idship}'

    def get_content(self, idship):
        r = requests.post(self.url, json={'criteria': [idship], 'shipped': False}, headers=self.headers, timeout=self.request_timeout)
        if r.status_code == 200:
            return r.json()

    def parse_content(self, json):
        events = []

        timeline = json[0]['events']
        for event in timeline:
            label = event['translatedLabelBC']
            location = event['location']['name']

            if label and location:
                location = location.replace('Hong Kong', 'HK')
                country = event['location']['countryCode']

                if country not in location:
                    location = ', '.join((location, country))

                date = datetime.utcfromtimestamp(event['date'] / 1000).replace(tzinfo=pytz.utc)

                events.append(dict(date=date, status=location, label=label))

        return events, {}


class MondialRelay(Courier):
    name = 'Mondial Relay'
    product = 'Colis'
    fromto = f'FR{Courier.r_arrow}FR'

    idship_validation = r'^\d{8}(\d{2})?(\d{2})?\-\d{5}$'
    idship_validation_msg = f'8, 10 {TXT.or_} 12 {TXT.digits}-{TXT.zipcode}'

    def get_url_for_browser(self, idship):
        number, zip_code = idship.split('-')
        return f'https://www.mondialrelay.fr/suivi-de-colis?numeroExpedition={number}&codePostal={zip_code}'

    def get_content(self, idship):
        url = self.get_url_for_browser(idship)
        r = requests.get(url, timeout=self.request_timeout)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)

    def parse_content(self, tree):
        events = []

        timeline = tree.xpath('//div[@class="infos-account"]')
        for events_by_days in timeline:
            elts = events_by_days.xpath('./div')
            date_text = elts[0].xpath('.//p//text()')[0]
            events_by_hours = elts[1].xpath('./div')

            for event in events_by_hours:
                elts = event.xpath('./div/p//text()')
                hour_text, label = elts[:2]
                date = datetime.strptime(f'{date_text} {hour_text}', '%d/%m/%Y %H:%M').replace(tzinfo=get_localzone())

                events.append(dict(date=date, label=label))

        return events, {}


class GLS(Courier):
    name = 'GLS'

    def get_url_for_browser(self, idship):
        return f'https://gls-group.eu/FR/fr/suivi-colis.html?match={idship}'

    def get_content(self, idship):
        url = f'https://gls-group.eu/app/service/open/rest/FR/fr/rstt001?match={idship}'
        r = requests.get(url, timeout=self.request_timeout)
        if r.status_code == 200:
            return r.json()

    def parse_content(self, json):
        events = []
        product = None
        fromto = None

        if shipments := json.get('tuStatus'):
            if len(shipments) > 0:
                shipment = shipments[0]
                if infos := shipment.get('infos'):
                    infos = dict((info['type'], info) for info in infos)
                    if product := infos.get('PRODUCT'):
                        product = product.get('value')

                        if weight := infos.get('WEIGHT'):
                            product += f" {weight.get('value')}"

                if history := shipment.get('history'):
                    countries = []

                    for event in history:
                        label = event['evtDscr']
                        address = event['address']

                        countries.append(address['countryCode'])
                        date = datetime.strptime(f"{event['date']} {event['time']}", '%Y-%m-%d %H:%M:%S').replace(tzinfo=get_localzone())
                        events.append(dict(date=date,
                                           status=f"{address['city']}, {address['countryName']}",
                                           label=label))

                    if len(countries) > 0:
                        fromto = f'{countries[-1]} {Courier.r_arrow}'
                        if len(countries) > 1:
                            fromto += countries[0]

        return events, dict(product=product, fromto=fromto)


class DPD(Courier):
    name = 'DPD'

    def get_url_for_browser(self, idship):
        return f'https://trace.dpd.fr/fr/trace/{idship}'

    def get_content(self, idship):
        url = self.get_url_for_browser(idship)
        r = requests.get(url, timeout=self.request_timeout)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)

    def parse_content(self, tree):
        events = []

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
            location = txts[3] if len(txts) == 4 else None

            events.append(dict(date=datetime.strptime(f'{date} {hour}', '%d/%m/%Y %H:%M').replace(tzinfo=get_localzone()),
                               status=location, label=label))

        return events, dict(product=product)


class NLPost(Courier):
    name = 'NL Post'

    def get_url_for_browser(self, idship):
        return f'https://postnl.post/Details?barcode={idship}'

    def get_content(self, idship):
        url = self.get_url_for_browser(idship)
        r = requests.get(url, timeout=self.request_timeout)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)

    def parse_content(self, tree):
        events = []

        timeline = tree.xpath('//tr[@class="first detail"]') + tree.xpath('//tr[@class="detail"]')
        for event in timeline:
            date, label = event.xpath('./td/text()')[:2]

            events.append(dict(date=datetime.strptime(date.strip(), '%d-%m-%Y %H:%M').replace(tzinfo=get_localzone()), label=label))

        return events, {}


class FourPX(Courier):
    name = '4PX'

    def get_url_for_browser(self, idship):
        return f'http://track.4px.com/query/{idship}?'

    def get_content(self, idship):
        url = self.get_url_for_browser(idship)
        r = requests.get(url, timeout=self.request_timeout)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)

    def parse_content(self, tree):
        events = []

        timeline = tree.xpath('//div[@class="track-container"]//li')
        for event in timeline:
            date, hour, label = [stxt for txt in event.xpath('.//text()') if (stxt := re.sub(r'[\n\t]', '', txt).strip().replace('\xa0', '')) != '']
            status, label = label.split('/', 1) if '/' in label else ('', label)

            events.append(dict(date=datetime.strptime(f'{date} {hour}', '%Y-%m-%d %H:%M').replace(tzinfo=pytz.utc),
                               status=status.strip(), label=label.strip()))

        return events, {}


class LaPoste(Courier):
    name = 'La Poste'

    idship_validation, idship_validation_msg = get_simple_validation(11, 15)
    headers = {'X-Okapi-Key': LaPoste_key, 'Accept': 'application/json'}

    codes = dict(
        DR1=('Déclaratif réceptionné', False),
        PC1=('Pris en charge', False),
        PC2=('Pris en charge dans le pays d’expédition', False),
        ET1=('En cours de traitement', False),
        ET2=('En cours de traitement dans le pays d’expédition', False),
        ET3=('En cours de traitement dans le pays de destination', False),
        ET4=('En cours de traitement dans un pays de transit', False),
        EP1=('En attente de présentation', False),
        DO1=('Entrée en Douane', False),
        DO2=('Sortie  de Douane', False),
        DO3=('Retenu en Douane', True),
        PB1=('Problème en cours', True),
        PB2=('Problème résolu', False),
        MD2=('Mis en distribution', False),
        ND1=('Non distribuable', True),
        AG1=("En attente d'être retiré au guichet", True),
        RE1=("Retourné à l'expéditeur", True),
        DI1=('Distribué', False),
        DI2=("Distribué à l'expéditeur", True)
    )

    def get_url_for_browser(self, idship):
        return f'https://www.laposte.fr/outils/suivre-vos-envois?code={idship}'

    def get_content(self, idship):
        url = f'https://api.laposte.fr/suivi/v2/idships/{idship}?lang=fr_FR'
        r = requests.get(url, headers=self.headers, timeout=self.request_timeout)
        if r.status_code == 200:
            return r.json()

    def parse_content(self, json):
        events = []

        shipment = json.get('shipment')
        if shipment:
            product = shipment.get('product').capitalize()

            ctx = shipment.get('contextData')
            if ctx:
                fromto = f"{ctx['originCountry']}{Courier.r_arrow}{ctx['arrivalCountry']}"
            else:
                fromto = None

            timeline = list(filter(lambda t: t['status'], shipment.get('timeline')))
            status_label = timeline[-1]['shortLabel']
            delivered = False

            for event in shipment.get('event', ()):
                code = event['code']
                event_delivered = code in ('DI1', 'DI2')
                delivered |= event_delivered

                status, warn = self.codes.get(code, '?')
                label = f"{get_sentence(event['label'], 1)}"

                events.append(dict(date=get_local_time(event['date']), status=status, warn=warn, label=label, delivered=event_delivered))

            status_warn = events[-1]['warn'] if events else False
            return events, dict(product=product,
                                fromto=fromto,
                                delivered=delivered,
                                status_warn=status_warn,
                                status_label=status_label.replace('.', '')
                                )

        else:
            error = json.get('returnMessage', 'Erreur')
            status_label = get_sentence(error, 1)
            return events, dict(status_warn=True, status_label=status_label.replace('.', ''))


@Scrapper(timeout=10)
class Chronopost(LaPoste):
    name = 'Chronopost'

    timeline_xpath = '//tr[@class="toggleElmt show"]'

    # use La Poste API to find out the url
    def get_url_for_browser(self, idship):
        json = super().get_content(idship)
        if json:
            return json.get('shipment', {}).get('urlDetail')

    #  do not return any selenium objects, the driver is disposed after
    def get_content(self, driver, idship):
        self.log(f'scrapper WAIT timeline - {idship}')
        timeline_locator = (By.XPATH, self.timeline_xpath)
        WebDriverWait(driver, self.timeout_elt).until(EC.presence_of_all_elements_located(timeline_locator))
        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, tree):
        events = []

        for tr in tree.xpath(self.timeline_xpath):
            tds = tr.xpath('./td')
            day, hour = tds[0].xpath('./text()')
            status, label = tds[1].xpath('./text()')
            day = day.split(' ', 1)[1]  # remove full day name
            date = datetime.strptime(f'{day} {hour}', '%d/%m/%Y %H:%M').replace(tzinfo=get_localzone())
            status = status.replace('...', '').strip()
            events.append(dict(date=date, status=status, label=label))

        return events, {}


class DHL(Courier):
    name = 'DHL'

    idship_validation, idship_validation_msg = r'^\d{10}$', f'10 {TXT.letters}'
    headers = {'Accept': 'application/json', 'DHL-API-Key': dhl_key}

    def get_url_for_browser(self, idship):
        return f'https://www.dhl.com/fr-en/home/our-divisions/parcel/private-customers/tracking-parcel.html?tracking-id={idship}'

    def get_content(self, idship):
        url = f'https://api-eu.dhl.com/track/shipments?trackingNumber={idship}&requesterCountryCode=FR'
        r = requests.get(url, headers=self.headers, timeout=self.request_timeout)
        return r.status_code == 200, r.json()

    def parse_content(self, json):
        events = []

        shipments = json.get('shipments')
        if shipments:
            shipment = shipments[0]
            product = f"DHL {shipment['service']}"

            for event in shipment['events']:
                events.append(dict(date=get_local_time(event['date']), label=event['description']))

            return events, dict(product=product)


if __name__ == '__main__':
    from config import couriers_tests
    from log import mylog

    mylog.print_only()

    couriers = Couriers()
    for name, idship in couriers_tests:
        result = couriers.get(name).update(idship)
        ok = True if result and result['ok'] else False
        print(f'{name} {idship} {ok=}')
        # if ok:
        #     import pprint
        #     pprint.pprint(result, indent=4)

    mylog.close()
