FROM python:3.11

ENV ALGOBATTLE_IO_VOLUMES=true
WORKDIR /src/algobattle
COPY . .
RUN pip install .

ENTRYPOINT [ "algobattle" ]
CMD ["-h"]
