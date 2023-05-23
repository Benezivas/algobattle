FROM rust:1.69

COPY . ~/solver
RUN [ "cargo", "install", "--path", "~/solver" ]

ENTRYPOINT [ "solver" ]
