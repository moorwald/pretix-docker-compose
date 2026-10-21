"""Read-only server-side release probe. Never executes a browser or Google code."""
import hashlib
import json
import logging
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from django.test import Client
from pretix.base.middleware import _parse_csp
from django_scopes import scope
from pretix.base.models import Organizer, Event, Order

logging.disable(logging.CRITICAL)
organizer = Organizer.objects.get(slug='Mautic')
with scope(organizer=organizer):
    event = Event.objects.get(organizer=organizer, slug='mwc2026')
with scope(organizer=organizer, event=event):
    order = Order.objects.filter(event=event, status='p', testmode=False, total__gt=0).first()
assert order is not None, 'No eligible existing paid order for read-only probe'

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.bridge = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and 'mwc-ads-bridge-v1.js' in attrs.get('src',''):
            self.bridge.append(attrs)

client = Client(raise_request_exception=False, HTTP_HOST='tickets.mautic.org')
url = '/Mautic/mwc2026/order/' + order.code + '/' + order.secret + '/'
response = client.get(url + '?paid=yes', secure=True)
assert response.status_code == 200, 'Confirmation did not render'
p = Parser(); p.feed(response.content.decode())
assert len(p.bridge) == 1, 'Bridge missing or duplicated'
assert Decimal(p.bridge[0]['data-value']) == order.total
assert p.bridge[0]['data-currency'] == event.currency
assert p.bridge[0]['data-transaction-id'] == 'Mautic-mwc2026-' + order.code
assert p.bridge[0]['referrerpolicy'] == 'no-referrer'
assert b'googletagmanager.com' not in response.content
assert 'https://mauticon.mautic.org' in response['Content-Security-Policy']
assert 'googletagmanager.com' not in response['Content-Security-Policy']
policy = _parse_csp(response['Content-Security-Policy'])
allowed = policy.get('script-src-elem', policy.get('script-src', policy['default-src']))
assert any(s == "'self'" or s == 'https:' or 'https://tickets.mautic.org/static/mwc-ads-bridge-v1.js'.startswith(s) for s in allowed), 'Bridge blocked by native script policy'
plain = client.get(url, secure=True)
assert plain.status_code == 200 and b'mwc-ads-bridge-v1.js' not in plain.content
print(json.dumps({'paid_confirmation_http':200,'dynamic_values_correct':True,'plain_receipt_without_tracking':True,
                  'google_not_in_private_document':True,'public_frame_allowed_by_native_csp':True,
                  'bridge_sha256':hashlib.sha256(Path('/pretix/src/pretix/static.dist/mwc-ads-bridge-v1.js').read_bytes()).hexdigest()}))
