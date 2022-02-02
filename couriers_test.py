from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from localization import TXT
from log import log, logger

MUTI_THREADED = False

COURIERS_IDSHIP = (
    ("USPS", "LZ596462615US"),
    ("DHL", "JVGL084127362550620461415537"),
    # ('DHL', '1234567890'),
    # ('DHL', '6294166480'),
    ("Relais Colis", "VD3410033223"),
    ("4PX", "LZ074882152FR"),
    ("Asendia", "LZ074882152FR"),
    ("Cainiao", "LZ074882152FR"),
    ("Chronopost", "DT201253687FR"),
    # ("DPD", "250063801848433"),
    ("DPD", "250092101363956"),
    ("GLS", "676411719238"),
    ("La Poste", "LZ074882152FR"),
    ("Mondial Relay", "11150623-34920"),
    ("NL Post", "LT666174269NL"),
)

if not MUTI_THREADED:

    class MockThreadPoolExecutor(ThreadPoolExecutor):
        def submit(self, f, *args, **kwargs):
            future = Future()
            future.set_result(f(*args, **kwargs))
            return future

        def shutdown(self, wait=True):
            pass

    ThreadPoolExecutor = MockThreadPoolExecutor


if __name__ == "__main__":
    # prevent drivers to be created in subprocess
    from couriers import CouriersHandler

    logger.print_only()
    logger.close()

    passed, failed = [], []
    couriers_handler = CouriersHandler(max_drivers=1)

    with ThreadPoolExecutor(max_workers=len(COURIERS_IDSHIP)) as executor:
        futures = {
            executor.submit(couriers_handler.update, courier_name, id_ship): courier_name
            for courier_name, id_ship in sorted(COURIERS_IDSHIP, key=lambda t: t[0])
        }

        for future in as_completed(futures):
            result = future.result()
            courier_name = futures[future]

            if result and result["ok"]:
                passed.append(courier_name)
                evt = result["events"][0]
                log(f"PASS test - {courier_name}", end="")
                status = evt["status"] + ", " if evt["status"] else ""
                log(f" - {evt['date']:{TXT.long_date_format}} - {status}{evt['label']}")

            else:
                failed.append(courier_name)
                log(f"FAIL test - {courier_name} !!!!!!!!!!!!!!!!!!!!!!!")

        def get_list_of_names(names):
            if not names:
                return "NONE"
            txt = "ALL " if len(names) == len(COURIERS_IDSHIP) else ""
            return f"{txt}{len(names)} ({', '.join(names)})"

        log()
        log(f"Passed: {get_list_of_names(passed)}")
        log(f"Failed: {get_list_of_names(failed)}")
        log()
