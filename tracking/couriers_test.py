from concurrent.futures import Future, ThreadPoolExecutor, as_completed

MUTI_THREADED = True

if not MUTI_THREADED:

    class MockThreadPoolExecutor(ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            function, *args = args
            future_ = Future()
            future_.set_result(function(*args, **kwargs))
            return future_

        def shutdown(self, wait=True):
            pass

    ThreadPoolExecutor = MockThreadPoolExecutor
    N_DRIVERS = 1

else:
    N_DRIVERS = 3


if __name__ == "__main__":
    from os import path, sys

    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

    from windows.localization import TXT
    from windows.log import log, logger

    # prevent drivers to be created in subprocess
    from tracking.couriers_handler import CouriersHandler

    # list of tuples (courier_name, idship)
    from tracking.secrets import Couriers_to_test

    logger.print_only()
    logger.close()

    passed, failed = [], []
    couriers_handler = CouriersHandler(max_drivers=N_DRIVERS)
    couriers_to_test = sorted(Couriers_to_test, key=lambda c: c[0])

    with ThreadPoolExecutor(max_workers=len(couriers_to_test)) as executor:
        futures = {
            executor.submit(couriers_handler.update, courier_name, idship): courier_name
            for courier_name, idship in couriers_to_test
        }

        for future in as_completed(futures):
            result = future.result()
            courier_name = futures[future]

            if result and result["ok"]:
                passed.append(courier_name)
                evt = result["events"][0]
                log(f". test PASS - {courier_name}", end="")
                status = f"{evt['status']}, " if evt["status"] else ""
                log(f" - {evt['date']:{TXT.long_date_format}} - {status}{evt['label']}")

            else:
                failed.append(courier_name)
                log(f". test FAIL - {courier_name} !!")

        def get_couriers_names(a_list):
            if a_list:
                txt = "ALL " if len(a_list) == len(couriers_to_test) else ""
                names = (f"\n . {name}" for name in sorted(a_list))
                return f"{txt}{len(a_list)}{''.join(names)}"
            return "NONE"

        log()
        log(f"Passed: {get_couriers_names(passed)}")
        log()
        log(f"Failed: {get_couriers_names(failed)}")
        log()
