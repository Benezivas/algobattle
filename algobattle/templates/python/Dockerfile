FROM python:3.11

WORKDIR /algobattle_src
COPY pyproject.toml .
COPY {{ program }}  {{ program }}
RUN pip install .

WORKDIR /
CMD [ "python", "-m", "{{ program }}.main" ]
