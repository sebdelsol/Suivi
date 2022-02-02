from concurrent.futures import Future, ThreadPoolExecutor, as_completed

MUTI_THREADED = True

COURIERS_TEST = (
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
    N_DRIVERS = 2

else:
    N_DRIVERS = 1


if __name__ == "__main__" and __package__ is None:
    from os import path, sys

    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

    from windows.localization import TXT
    from windows.log import log, logger

    # prevent drivers to be created in subprocess
    from tracking.couriers import CouriersHandler

    logger.print_only()
    logger.close()

    passed, failed = [], []
    couriers_handler = CouriersHandler(max_drivers=N_DRIVERS)
    couriers_test = sorted(COURIERS_TEST, key=lambda c: c[0])

    with ThreadPoolExecutor(max_workers=len(couriers_test)) as executor:
        futures = {
            executor.submit(couriers_handler.update, courier_name, id_ship): courier_name
            for courier_name, id_ship in couriers_test)
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

        def get_list_of_names(type_):
            if not type_:
                return "NONE"
            txt = "ALL " if len(type_) == len(couriers_test) else ""
            return f"{txt}{len(type_)} ({', '.join(type_)})"

        log()
        log(f"Passed: {get_list_of_names(passed)}")
        log(f"Failed: {get_list_of_names(failed)}")
        log()
