FROM pretix/standalone:2026.2.0

# Bundle the temporary confirmation hook in the image, not in /data or host binds.
# Preserve the exact upstream template so all original order rendering remains intact.
USER root
RUN cp /pretix/src/pretix/presale/templates/pretixpresale/event/order.html \
       /pretix/src/pretix/presale/templates/pretixpresale/event/mwc-order-original.html
COPY tracking/templates/pretixpresale/event/order.html /pretix/src/pretix/presale/templates/pretixpresale/event/order.html
COPY tracking/assets/mwc-ads-confirmation-v1.js /pretix/src/pretix/static.dist/mwc-ads-confirmation-v1.js
USER pretixuser
