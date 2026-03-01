FROM pretix/standalone:2026.2.0

USER root
RUN pip3 install pretix-custom-css-js
USER pretixuser
RUN cd /pretix/src && python -m pretix migrate --no-input
