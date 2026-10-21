import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import django
from django.conf import settings
from django.template import Context, Engine

if not settings.configured:
    settings.configure(USE_I18N=False, INSTALLED_APPS=[])
    django.setup()

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = 'pretixpresale/event/order.html'


class ConfirmationTemplateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        upstream = Path(cls.temp.name) / 'pretixpresale/event/mwc-order-original.html'
        upstream.parent.mkdir(parents=True)
        upstream.write_text('{% block content %}<h1>Original order details</h1>{% endblock %}')
        cls.engine = Engine(
            dirs=[str(ROOT / 'tracking/templates'), cls.temp.name],
            libraries={'l10n': 'django.templatetags.l10n'},
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def render(self, *, status='p', total='123.45', testmode=False,
               event='mwc2026', organizer='Mautic', query=None, backend_user=False, code='ABCDE'):
        request = SimpleNamespace(
            organizer=SimpleNamespace(slug=organizer),
            event=SimpleNamespace(slug=event, currency='GBP'),
            GET={'thanks': 'yes'} if query is None else query,
        )
        order = SimpleNamespace(status=status, total=Decimal(total), testmode=testmode, code=code)
        return self.engine.get_template(TEMPLATE).render(Context({
            'request': request, 'order': order, 'backend_user': backend_user,
        }))

    def test_paid_confirmation_keeps_original_and_adds_order_values(self):
        html = self.render()
        self.assertIn('<h1>Original order details</h1>', html)
        self.assertIn('/static/mwc-ads-confirmation-v1.js', html)
        self.assertIn('data-value="123.45"', html)
        self.assertIn('data-currency="GBP"', html)
        self.assertIn('data-transaction-id="Mautic-mwc2026-ABCDE"', html)
        self.assertNotIn('googletagmanager.com', html)  # Loading Google requires consent in the external script.

    def test_paid_return_marker(self):
        self.assertIn('mwc-ads-confirmation', self.render(query={'paid': 'yes'}))

    def test_no_measurement_for_free_pending_cancelled_test_or_old_order_view(self):
        cases = [
            {'total': '0'}, {'status': 'n'}, {'status': 'c'}, {'status': 'e'},
            {'testmode': True}, {'query': {}}, {'backend_user': True},
            {'event': 'another-event'}, {'organizer': 'another-organizer'},
        ]
        for case in cases:
            with self.subTest(case=case):
                html = self.render(**case)
                self.assertIn('Original order details', html)
                self.assertNotIn('mwc-ads-confirmation', html)

    def test_attribute_escaping(self):
        html = self.render(code='ABC"><script>bad()</script>')
        self.assertNotIn('<script>bad()', html)
        self.assertIn('&quot;&gt;&lt;script&gt;', html)


if __name__ == '__main__':
    unittest.main()
