FROM alpine

# causes an execution timeout.
COPY solution.json /solution.json
ENTRYPOINT mv /solution.json /output/solution.json && sleep 6000
