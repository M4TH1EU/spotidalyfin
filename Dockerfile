# Pull the baseimage.
FROM jlesage/baseimage-gui:alpine-3.22

RUN add-pkg python3 py3-pip git

RUN git clone -b feat-refactor https://github.com/M4TH1EU/syncphony.git

RUN pip3 install --no-cache-dir --break-system-packages --root-user-action ignore -r syncphony/requirements.txt

# Copy the start script.
COPY startapp.sh /startapp.sh

# Set the application name.
RUN set-cont-env APP_NAME "Syncphony"
