FROM python:3.11

WORKDIR /src/algobattle
COPY . .
RUN pip install .

ENTRYPOINT [ "algobattle" ]
CMD ["-h"]
