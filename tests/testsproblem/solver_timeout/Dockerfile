FROM alpine

# causes an execution timeout.
COPY solution.json /solution.json
ENTRYPOINT mkdir /output; mv /solution.json /output/solution.json && sleep 6000
