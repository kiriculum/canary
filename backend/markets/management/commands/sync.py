from django.core.management.base import BaseCommand, CommandParser

from markets.management.executor import SyncExecutor


class Command(BaseCommand):
    help = 'Fetch and store data'
    requires_system_checks = []
    suppressed_base_arguments = {'--version', '--verbosity', '--settings', '--pythonpath', '--traceback', '--no-color',
                                 '--force-color', '--skip-checks'}

    def add_arguments(self, parser: CommandParser):
        parser.add_argument('type', choices=SyncExecutor.types)

    def handle(self, *args, **options):
        SyncExecutor.execute(options['type'])
