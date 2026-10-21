FROM pretix/standalone:2026.8.0
COPY maintenance/pretix-hold.conf /etc/mwc-maintenance.conf

# Minimal override, with the exact 2026.8.0 order template preserved as its parent.
# The hash intentionally fails the build if an upstream update needs a review.
USER root
RUN echo 'e465e46037b01be750b77980cdfee7f61d7d2a76e5710713d6b81e1f7d98f9b4  /pretix/src/pretix/presale/templates/pretixpresale/event/order.html' | sha256sum -c - \
    && cp /pretix/src/pretix/presale/templates/pretixpresale/event/order.html /pretix/src/pretix/presale/templates/pretixpresale/event/mwc-order-original.html
COPY tracking/templates/pretixpresale/event/order.html /pretix/src/pretix/presale/templates/pretixpresale/event/order.html
COPY tracking/assets/mwc-ads-bridge-v1.js /pretix/src/pretix/static.dist/mwc-ads-bridge-v1.js
COPY tracking/probe_confirmation.py /pretix/src/mwc_confirmation_probe.py
USER pretixuser
