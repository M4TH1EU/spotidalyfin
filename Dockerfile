# Pull the baseimage.
FROM jlesage/baseimage-gui:alpine-3.22-v4

RUN add-pkg python3 py3-pip git chromium

RUN #git clone -b feat-refactor https://github.com/M4TH1EU/syncphony.git /syncphony
COPY . /syncphony

RUN pip3 install --no-cache-dir --break-system-packages --root-user-action ignore -r /syncphony/requirements.txt

RUN chmod -R 777 /syncphony/ # not ideal

# Copy the start script.
COPY startapp.sh /startapp.sh
RUN chmod +x /startapp.sh

# Set the application name.
RUN set-cont-env APP_NAME "Syncphony"

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health