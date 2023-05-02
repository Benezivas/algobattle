FROM alpine

# outputs a static instance and certificate
COPY instance.json /instance.json
ENTRYPOINT mkdir /output; mv /instance.json /output/instance.json && sleep 6000
