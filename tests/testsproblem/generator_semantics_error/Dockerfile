FROM alpine

# outputs a static string encoding an instance with an artificially wrong certificate.
COPY instance.json /instance.json
ENTRYPOINT mv /instance.json /output/instance.json
