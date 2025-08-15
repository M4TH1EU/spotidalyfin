# Pull the baseimage.
FROM jlesage/baseimage-gui:alpine-3.22-v4

RUN add-pkg python3 py3-pip git chromium

RUN git clone -b feat-refactor https://github.com/M4TH1EU/syncphony.git /root/syncphony
#COPY . /root/syncphony # for local development debug

RUN pip3 install --no-cache-dir --break-system-packages --root-user-action ignore -r /root/syncphony/requirements.txt

RUN echo '[general]\nemail = "a@a.a"' > /root/.streamlit/credentials.toml # fix streamlit "welcome"

# Copy the start script.
COPY startapp.sh /startapp.sh

# Set the application name.
RUN set-cont-env APP_NAME "Syncphony"