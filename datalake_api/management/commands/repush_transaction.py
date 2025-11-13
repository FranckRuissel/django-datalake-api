from django.core.management.base import BaseCommand
from django.conf import settings
import os, json, subprocess, datetime

class Command(BaseCommand):
    help = 'Repush a transaction back to Kafka using local producer script'

    def add_arguments(self, parser):
        parser.add_argument('transaction_id', type=str)

    def handle(self, *args, **options):
        txid = options['transaction_id']
        root = settings.DATA_LAKE_ROOT
        found = None
        for dirpath, dirs, files in os.walk(root):
            for fname in files:
                if fname.endswith(('.json','.jsonl')):
                    fp = os.path.join(dirpath, fname)
                    with open(fp,'r',encoding='utf-8') as f:
                        try:
                            obj = json.load(f)
                            arr = obj if isinstance(obj, list) else [obj]
                        except Exception:
                            f.seek(0)
                            arr = []
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    arr.append(json.loads(line))
                                except Exception:
                                    pass
                        for rec in arr:
                            if str(rec.get('transaction_id'))==str(txid):
                                found = rec
                                break
                if found:
                    break
            if found:
                break
        if not found:
            self.stdout.write(self.style.ERROR('transaction not found'))
            return
        found['timestamp'] = datetime.datetime.utcnow().isoformat()
        producer_script = os.path.join(settings.BASE_DIR.parent, 'kafka_project_pipeline', 'producer.py')
        if os.path.exists(producer_script):
            p = subprocess.Popen(['python3', producer_script], stdin=subprocess.PIPE)
            p.stdin.write(json.dumps(found).encode('utf-8'))
            p.stdin.close()
            p.wait()
            self.stdout.write(self.style.SUCCESS('repushed'))
        else:
            self.stdout.write(self.style.ERROR('producer script not found at %s' % producer_script))
