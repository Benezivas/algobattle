"""Creates the config objects."""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
import tomllib
from types import EllipsisType
from typing import Any, ClassVar, Literal, Self, Type, TypeAlias
from typing_extensions import TypedDict

from pydantic import ConfigDict, Field, GetCoreSchemaHandler, model_validator, BaseModel as PydanticBase
from pydantic_core import CoreSchema
from pydantic_core.core_schema import no_info_after_validator_function, tagged_union_schema
from docker.types import LogConfig, Ulimit

from algobattle.problem import ProblemName
from algobattle.util import BaseModel, ByteSizeInt, MatchMode, RelativeFilePath, RelativePath, TimeDeltaFloat, WithNone


class _Adapter:
    """Turns a docker library config class into a pydantic parseable one."""

    _Args: ClassVar[type[TypedDict]]

    @classmethod
    def _construct(cls, kwargs: dict[str, Any]) -> Self:
        return cls(**kwargs)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type, handler: GetCoreSchemaHandler) -> CoreSchema:
        return no_info_after_validator_function(cls._construct, handler(cls._Args))


class PydanticLogConfig(LogConfig, _Adapter):  # noqa: D101
    class _Args(TypedDict):
        type: str
        conifg: dict[Any, Any]


class PydanticUlimit(Ulimit, _Adapter):  # noqa: D101
    class _Args(TypedDict):
        name: str
        soft: int
        hard: int


class AdvancedRunArgs(BaseModel):
    """Advanced docker run options.

    Contains all options exposed on the python docker run api, except `device_requests`
    and those set by :meth:`Image.run` itself.
    """

    class _BlockIOWeight(TypedDict):
        Path: str
        Weight: int

    class _DeviceRate(TypedDict):
        Path: str
        Rate: int

    class _HealthCheck(TypedDict):
        test: list[str] | str
        interval: int
        timeout: int
        retries: int
        start_period: int

    # defaults set by us
    network_mode: str = "none"

    # actual docker defaults
    command: str | list[str] | None = None
    auto_remove: bool | None = None
    blkio_weight_device: list[_BlockIOWeight] | None = None
    blkio_weight: int | None = Field(default=None, ge=10, le=1000)
    cap_add: list[str] | None = None
    cap_drop: list[str] | None = None
    cgroup_parent: str | None = None
    cgroupns: str | None = None
    cpu_count: int | None = None
    cpu_percent: int | None = None
    cpu_period: int | None = None
    cpu_quota: int | None = None
    cpu_rt_period: int | None = None
    cpu_rt_runtime: int | None = None
    cpu_shares: int | None = None
    cpuset_mems: str | None = None
    device_cgroup_rules: list[str] | None = None
    device_read_bps: list[_DeviceRate] | None = None
    device_read_iops: list[_DeviceRate] | None = None
    device_write_bps: list[_DeviceRate] | None = None
    device_write_iops: list[_DeviceRate] | None = None
    devices: list[str] | None = None
    dns: list[str] | None = None
    dns_opt: list[str] | None = None
    dns_search: list[str] | None = None
    domainname: str | list[str] | None = None
    entrypoint: str | list[str] | None = None
    environment: dict[str, str] | list[str] | None = None
    extra_hosts: dict[str, str] | None = None
    group_add: list[str] | None = None
    healthcheck: _HealthCheck | None = None
    hostname: str | None = None
    init: bool | None = None
    init_path: str | None = None
    ipc_mode: str | None = None
    isolation: str | None = None
    kernel_memory: int | str | None = None
    labels: dict[str, str] | list[str] | None = None
    links: dict[str, str] | None = None
    log_config: PydanticLogConfig | None = None
    lxc_conf: dict[Any, Any] | None = None
    mac_address: str | None = None
    mem_limit: int | str | None = None
    mem_reservation: int | str | None = None
    mem_swappiness: int | None = None
    memswap_limit: str | int | None = None
    network: str | None = None
    network_disabled: bool | None = None
    oom_kill_disable: bool | None = None
    oom_score_adj: int | None = None
    pid_mode: str | None = None
    pids_limit: int | None = None
    platform: str | None = None
    ports: dict[Any, Any] | None = None
    privileged: bool | None = None
    publish_all_ports: bool | None = None
    read_only: bool | None = None
    restart_policy: dict[Any, Any] | None = None
    runtime: str | None = None
    security_opt: list[str] | None = None
    shm_size: str | int | None = None
    stdin_open: bool | None = None
    stdout: bool | None = None
    stderr: bool | None = None
    stop_signal: str | None = None
    storage_opt: dict[Any, Any] | None = None
    stream: bool | None = None
    sysctls: dict[Any, Any] | None = None
    tmpfs: dict[Any, Any] | None = None
    tty: bool | None = None
    ulimits: list[PydanticUlimit] | None = None
    use_config_proxy: bool | None = None
    user: str | int | None = None
    userns_mode: str | None = None
    uts_mode: str | None = None
    version: str | None = None
    volume_driver: str | None = None
    volumes: dict[Any, Any] | list[Any] | None = None
    volumes_from: list[Any] | None = None
    working_dir: str | None = None

    @cached_property
    def kwargs(self) -> dict[str, Any]:
        """Transforms the object into :meth:`client.containers.run` kwargs."""
        return self.model_dump(exclude_none=True)


class AdvancedBuildArgs(BaseModel):
    """Advanced docker build options.

    Contains all options exposed on the python docker build api, except those set by :meth:`Image.build` itself.
    """

    class _ContainerLimits(TypedDict):
        memory: int
        memswap: int
        cpushares: int
        cpusetcpus: str

    # defaults set by us
    rm: bool = True
    forcerm: bool = True
    quiet: bool = True
    network_mode: str = "host"
    pull: bool | None = True

    # actual Docker defaults
    nocache: bool | None = None
    encoding: str | None = None
    buildargs: dict[Any, Any] | None = None
    container_limits: _ContainerLimits | None = None
    shmsize: int | None = None
    labels: dict[Any, Any] | None = None
    cache_from: list[Any] | None = None
    target: str | None = None
    squash: bool | None = None
    extra_hosts: dict[Any, Any] | None = None
    platform: str | None = None
    isolation: str | None = None
    use_config_proxy: bool | None = None

    @cached_property
    def kwargs(self) -> dict[str, Any]:
        """Transforms the object into :meth:`client.images.build` kwargs."""
        return self.model_dump(exclude_none=True)


class DockerConfig(BaseModel):
    """Settings passed directly to the docker daemon."""

    build: AdvancedBuildArgs = AdvancedBuildArgs()
    run: AdvancedRunArgs = AdvancedRunArgs()


class RunConfigOverride(TypedDict, total=False):
    """Run parameters that were overriden by the battle type."""

    timeout: float | None
    space: int | None
    cpus: int


@dataclass(frozen=True, slots=True)
class RunSpecs:
    """Actual specification of a program run."""

    timeout: float | None
    space: int | None
    cpus: int
    overriden: RunConfigOverride


class RunConfig(BaseModel):
    """Parameters determining how a program is run."""

    timeout: WithNone[TimeDeltaFloat] = 30
    """Timeout in seconds, or `false` for no timeout."""
    space: WithNone[ByteSizeInt] = None
    """Maximum memory space available, or `false` for no limitation.

    Can be either an plain number of bytes like `30000` or a string including
    a unit like `30 kB`.
    """
    cpus: int = 1
    """Number of cpu cores available."""

    def reify(
        self,
        timeout: float | None | EllipsisType,
        space: int | None | EllipsisType,
        cpus: int | EllipsisType,
    ) -> RunSpecs:
        """Merges the overriden config options with the parsed ones."""
        overriden = RunConfigOverride()
        if timeout is ...:
            timeout = self.timeout
        else:
            overriden["timeout"] = timeout
        if space is ...:
            space = self.space
        else:
            overriden["space"] = space
        if cpus is ...:
            cpus = self.cpus
        else:
            overriden["cpus"] = cpus
        return RunSpecs(timeout=timeout, space=space, cpus=cpus, overriden=overriden)


class MatchConfig(BaseModel):
    """Parameters determining the match execution.

    It will be parsed from the given config file and contains all settings that specify how the match is run.
    """

    problem: ProblemName | RelativeFilePath = Field(default=Path("problem.py"), validate_default=True)
    """The problem this match is over.

    Either the name of an installed problem, or the path to a problem file
    """
    build_timeout: WithNone[TimeDeltaFloat] = 600
    """Timeout for building each docker image."""
    image_size: WithNone[ByteSizeInt] = None
    """Maximum size a built program image is allowed to be."""
    strict_timeouts: bool = False
    """Whether to raise an error if a program runs into the timeout."""
    generator: RunConfig = RunConfig()
    solver: RunConfig = RunConfig()

    model_config = ConfigDict(revalidate_instances="always")


class ExecutionConfig(BaseModel):
    """Settings that only determine how a match is run, not its result."""

    parallel_battles: int = 1
    """Number of battles exectuted in parallel."""
    mode: MatchMode = "testing"
    """Mode of the match."""
    set_cpus: str | list[str] | None = None
    """Wich cpus to run programs on, if a list is specified each battle will use a different cpu specification in it."""
    points: int = 100
    """Highest number of points each team can achieve."""

    @model_validator(mode="after")
    def val_set_cpus(self) -> Self:
        """Validates that each battle that is being executed is assigned some cpu cores."""
        if isinstance(self.set_cpus, list) and self.parallel_battles > len(self.set_cpus):
            raise ValueError("Number of parallel battles exceeds the number of set_cpu specifier strings.")
        else:
            return self


class TeamInfo(BaseModel):
    """The config parameters defining a team."""

    generator: RelativePath
    solver: RelativePath


TeamInfos: TypeAlias = dict[str, TeamInfo]


class BattleConfig(BaseModel):
    """Config object for each specific battle type.

    A custom battle type can override this class to specify config options it uses. They will be parsed from a
    dictionary located at `battle` in the main config file. The created object will then be passed to the
    :meth:`Battle.run` method with its fields set accordingly.
    """

    type: str
    """Type of battle that will be used."""

    _children: ClassVar[list[Type[Self]]] = []

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        BattleConfig._children.append(cls)
        BattleConfig.model_rebuild(force=True)
        return super().__pydantic_init_subclass__(**kwargs)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Type[PydanticBase], handler: GetCoreSchemaHandler) -> CoreSchema:
        # there's two bugs we need to catch:
        # 1. this function is called during the pydantic BaseModel metaclass's __new__, so the BattleConfig class
        # won't be ready at that point and be missing in the namespace
        # 2. pydantic uses the core schema to build child classes core schema. for them we want to behave like a
        # normal model, only our own schema gets modified
        try:
            if cls != BattleConfig:
                return handler(source)
        except NameError:
            return handler(source)
        try:
            children = cls._children
        except AttributeError:
            children = []
        match len(children):
            case 0:
                return handler(source)
            case 1:
                return handler(children[0])
            case _:
                return tagged_union_schema(
                    choices={
                        subclass.model_fields["type"].default: subclass.__pydantic_core_schema__
                        for subclass in children
                    },
                    discriminator="type",
                )


# need to define this here to get nicer defaults
class IteratedConfig(BattleConfig):
    """Config options for Iterated battles."""

    type: Literal["Iterated"] = "Iterated"

    rounds: int = 5
    """Number of times the instance size will be increased until the solver fails to produce correct solutions."""
    maximum_size: int = 50_000
    """Maximum instance size that will be tried."""
    exponent: int = 2
    """Determines how quickly the instance size grows."""
    minimum_score: float = 1
    """Minimum score that a solver needs to achieve in order to pass."""


class AlgobattleConfigBase(BaseModel):
    """Base that contains all config options and can be parsed from config files."""

    # funky defaults to force their validation with context info present
    teams: TeamInfos = Field(
        default={"team_0": {"generator": Path("generator"), "solver": Path("solver")}}, validate_default=True
    )
    execution: ExecutionConfig = Field(default_factory=dict, validate_default=True)
    match: MatchConfig = Field(default_factory=dict, validate_default=True)
    battle: BattleConfig = IteratedConfig()
    docker: DockerConfig = DockerConfig()

    model_config = ConfigDict(revalidate_instances="always")

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Parses a config object from a toml file.

        If the file doesn't exist it returns a default instance instead of raising an error.
        """
        if not file.is_file():
            config_dict = {}
        else:
            with open(file, "rb") as f:
                try:
                    config_dict = tomllib.load(f)
                except tomllib.TOMLDecodeError as e:
                    raise ValueError(f"The config file at {file} is not a properly formatted TOML file!\n{e}")
        return cls.model_validate(config_dict, context={"base_path": file.parent})
