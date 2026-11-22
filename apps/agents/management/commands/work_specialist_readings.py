"""Process independent source readings without delaying the native workflow worker."""

import signal
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Event

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connections

from apps.agents import specialist_coordination, specialist_memory


def run_once():
    return specialist_coordination.run_once() or specialist_memory.run_once()


class Command(BaseCommand):
    help = "Run bounded background source readers. PostgreSQL owns task leases and work budgets."

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--workers", type=int, default=2)

    def handle(self, *args, **options):
        if not 1 <= options["workers"] <= 8:
            raise CommandError("Choose between one and eight source readers.")
        if not options["watch"]:
            self.stdout.write("Source reading processed" if run_once() else "Source reading queue idle")
            return
        self.stdout.write(f"Starting {options['workers']} background source readers.")
        stop = Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())

        def consume():
            try:
                while not stop.is_set():
                    close_old_connections()
                    if not run_once():
                        stop.wait(3)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=options["workers"]) as pool:
            readers = [pool.submit(consume) for _ in range(options["workers"])]
            try:
                done, _ = wait(readers, return_when=FIRST_COMPLETED)
                for reader in done:
                    reader.result()
            finally:
                stop.set()
