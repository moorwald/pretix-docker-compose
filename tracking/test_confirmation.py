"""Run through maintenance.qa_pretix against the offline restored database only."""
EXTRA_CHECK = r'''
print("MWC_QA_STAGE purchase_bridge", flush=True)
from decimal import Decimal
from types import SimpleNamespace as NS
from django.template import Context
from django.template.loader import get_template
from django.template.loader_tags import BlockNode
from django.template.defaulttags import IfNode
from pretix.base.middleware import _parse_csp
from html.parser import HTMLParser

class BridgeParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.bridge = []
    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'script' and 'mwc-ads-bridge-v1.js' in data.get('src', ''):
            self.bridge.append(data)

template = get_template('pretixpresale/event/order.html').template
header = next(n for n in template.nodelist.get_nodes_by_type(BlockNode) if n.name == 'custom_header')
# Exercise the real conditional AST independently; block.super requires inheritance,
# which the complete restored-order HTTP check below exercises separately.
eligibility = header.nodelist.get_nodes_by_type(IfNode)[0]
def render_header(**changes):
    values = dict(status='p', total=Decimal('123.45'), testmode=False, backend=False,
                  thanks=True, event='mwc2026', organizer='Mautic')
    values.update(changes)
    request = NS(GET={'paid':'yes'} if values['thanks'] else {},
                 organizer=NS(slug=values['organizer']), event=NS(slug=values['event'], currency='GBP'))
    context = Context({'request':request,'order':NS(code='ABCDE',status=values['status'],
                     total=values['total'],testmode=values['testmode']),'backend_user':values['backend']})
    with context.bind_template(template):
        result = eligibility.render(context)
    parser = BridgeParser();parser.feed(result)
    return parser.bridge
assert len(render_header()) == 1
assert render_header()[0]['data-value'] == '123.45'
assert render_header()[0]['data-transaction-id'] == 'Mautic-mwc2026-ABCDE'
for invalid in [dict(status='n'),dict(status='c'),dict(status='e'),dict(total=Decimal('0')),
                dict(testmode=True),dict(backend=True),dict(thanks=False),dict(event='another'),dict(organizer='another')]:
    assert not render_header(**invalid), 'Ineligible template context contains a purchase bridge'
with scope(organizer=organizer,event=event):
    order = Order.objects.filter(event=event,status='p',testmode=False,total__gt=0).first()
assert order is not None
private_path='/Mautic/mwc2026/order/'+order.code+'/'+order.secret+'/'
r=Client(raise_request_exception=False,HTTP_HOST='tickets.mautic.org').get(private_path+'?paid=yes',secure=True)
assert r.status_code == 200
parser=BridgeParser();parser.feed(r.content.decode())
assert len(parser.bridge)==1
assert Decimal(parser.bridge[0]['data-value'])==order.total
assert parser.bridge[0]['data-currency']==event.currency
assert parser.bridge[0]['data-transaction-id']=='Mautic-mwc2026-'+order.code
assert parser.bridge[0]['referrerpolicy']=='no-referrer'
assert b'googletagmanager.com' not in r.content
assert b'gtag(' not in r.content
policy=_parse_csp(r['Content-Security-Policy'])
assert 'https://mauticon.mautic.org' in policy['frame-src']
assert 'https://www.googletagmanager.com' not in policy.get('script-src',[])
assert b'mwc-ads-bridge-v1.js' not in Client(HTTP_HOST='tickets.mautic.org').get(private_path,secure=True).content
print('MWC_QA_EXTRA '+json.dumps({'paid_order_http':200,'dynamic_total_currency_id':True,
      'negative_template_contexts':9,'native_csp_merge_passed':True,'google_not_in_order_document':True}))
'''

if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'maintenance'))
    from qa_pretix import main
    main(Path(sys.argv[1]).resolve(), 'mwc-pretix-relay-qa', EXTRA_CHECK,
         {'PRETIX_PRETIX_CSP_ADDITIONAL_HEADER': 'frame-src https://mauticon.mautic.org'})
