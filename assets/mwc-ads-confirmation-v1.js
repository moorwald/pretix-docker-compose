/* Temporary MWC 2026 purchase-confirmation snippet, not a general Pretix plugin. */
(function () {
  'use strict';
  const purchase = document.currentScript.dataset;
  const consentCookie = document.cookie.split(';').map(function (cookie) {
    return cookie.trim();
  }).find(function (cookie) { return cookie.startsWith('mwc_consent='); });
  if (!consentCookie) return;
  let consent;
  try {
    consent = JSON.parse(decodeURIComponent(consentCookie.slice('mwc_consent='.length)));
  } catch (error) {
    console.warn('Invalid conference consent cookie; conversion tracking stays disabled.');
    return;
  }
  if (!consent || consent['google-ads'] !== true) return;

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
  window.gtag('consent', 'default', {
    ad_storage: 'granted',
    ad_user_data: 'granted',
    ad_personalization: 'denied',
    analytics_storage: 'denied'
  });
  // Keep the private order URL, access secret and referrer out of measurement fields.
  window.gtag('set', {
    ads_data_redaction: true,
    page_location: 'https://tickets.mautic.org/Mautic/mwc2026/',
    page_referrer: '',
    page_title: 'Mautic World Conference purchase confirmation'
  });
  window.gtag('js', new Date());
  window.gtag('config', 'AW-960227364', {
    cookie_domain: 'mautic.org',
    send_page_view: false,
    allow_google_signals: false,
    allow_ad_personalization_signals: false
  });
  window.gtag('event', 'conversion', {
    send_to: 'AW-960227364/-8CLCIO2obwCEKTQ78kD',
    value: Number(purchase.value),
    currency: purchase.currency,
    transaction_id: purchase.transactionId
  });
  const script = document.createElement('script');
  script.async = true;
  script.referrerPolicy = 'no-referrer';
  script.src = 'https://www.googletagmanager.com/gtag/js?id=AW-960227364';
  script.onerror = function () {
    console.warn('Google Ads tag could not load; this purchase may not be measured.');
  };
  document.head.appendChild(script);
}());
