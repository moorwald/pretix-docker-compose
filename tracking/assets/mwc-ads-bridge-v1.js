/* No Google code in this document. Never read or transmit the order URL. */
(function () {
  'use strict';
  const script = document.currentScript;
  const origin = 'https://mauticon.mautic.org';
  const message = {
    type: 'mwc.ads.purchase.v1',
    transactionId: script.dataset.transactionId,
    value: Number(script.dataset.value),
    currency: script.dataset.currency
  };
  if (!/^Mautic-mwc2026-[A-Z0-9]{5,16}$/.test(message.transactionId) ||
      !Number.isFinite(message.value) || message.value <= 0 || !/^[A-Z]{3}$/.test(message.currency)) return;

  function consent() {
    const entry = document.cookie.split(';').map(s => s.trim()).find(s => s.startsWith('mwc_consent='));
    if (!entry) return false;
    try { return JSON.parse(decodeURIComponent(entry.slice(12)))['google-ads'] === true; }
    catch (_) { return false; } // Missing/malformed consent always denies measurement.
  }
  let frame = null;
  let acknowledged = false;
  function update() {
    if (!consent()) {
      if (frame) frame.remove();
      frame = null;
      return;
    }
    if (acknowledged || frame) return;
    frame = document.createElement('iframe');
    frame.hidden = true;
    frame.title = 'Optional advertising measurement';
    frame.referrerPolicy = 'no-referrer';
    frame.src = origin + '/ads-conversion/'; // No order data or identifiers in the URL.
    frame.addEventListener('load', function () {
      if (consent() && frame) frame.contentWindow.postMessage(message, origin);
    });
    document.body.appendChild(frame);
  }
  window.addEventListener('message', function (event) {
    if (!frame || event.origin !== origin || event.source !== frame.contentWindow || !consent()) return;
    if (event.data && event.data.type === 'mwc.ads.queued.v1' && event.data.transactionId === message.transactionId) {
      acknowledged = true; // Acknowledges queuing, NOT Google attribution or payment verification.
    }
  });
  update();
  window.setInterval(update, 500); // Also observes shared-cookie consent/withdrawal from the parent site.
  window.addEventListener('pageshow', update);
}());
