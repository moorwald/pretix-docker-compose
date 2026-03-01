FROM pretix/standalone:2026.2.0

USER root
RUN pip3 install --no-build-isolation git+https://github.com/pretix-unofficial/pretix-custom-css-js.git
USER pretixuser
RUN cd /pretix/src && make production
