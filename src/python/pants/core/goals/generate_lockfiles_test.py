# Copyright 2022 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from typing import Iterable

import pytest

from pants.backend.python.subsystems.setup import PythonSetup
from pants.backend.python.target_types import (
    PythonRequirementsField,
    PythonRequirementTarget,
    PythonResolveField,
    PythonSourceField,
    PythonSourceTarget,
)
from pants.build_graph.address import Address
from pants.core.goals.generate_lockfiles import (
    DEFAULT_TOOL_LOCKFILE,
    NO_TOOL_LOCKFILE,
    AmbiguousResolveNamesError,
    GenerateLockfile,
    GenerateLockfileWithEnvironments,
    GenerateToolLockfileSentinel,
    KnownUserResolveNames,
    NoCompatibleResolveException,
    RequestedUserResolveNames,
    UnrecognizedResolveNamesError,
    WrappedGenerateLockfile,
    _preferred_environment,
    determine_resolves_to_generate,
    filter_tool_lockfile_requests,
)
from pants.engine.environment import EnvironmentName
from pants.engine.target import Dependencies, Target
from pants.testutil.option_util import create_subsystem
from pants.util.strutil import softwrap


def test_determine_tool_sentinels_to_generate() -> None:
    class Tool1(GenerateToolLockfileSentinel):
        resolve_name = "tool1"

    class Tool2(GenerateToolLockfileSentinel):
        resolve_name = "tool2"

    class Tool3(GenerateToolLockfileSentinel):
        resolve_name = "tool3"

    class Lang1Requested(RequestedUserResolveNames):
        pass

    class Lang2Requested(RequestedUserResolveNames):
        pass

    lang1_resolves = KnownUserResolveNames(
        ("u1", "u2"), option_name="[lang1].resolves", requested_resolve_names_cls=Lang1Requested
    )
    lang2_resolves = KnownUserResolveNames(
        ("u3",), option_name="[lang2].resolves", requested_resolve_names_cls=Lang2Requested
    )

    def assert_chosen(
        requested: set[str],
        expected_user_resolves: list[RequestedUserResolveNames],
        expected_tools: list[type[GenerateToolLockfileSentinel]],
    ) -> None:
        user_resolves, tools = determine_resolves_to_generate(
            [lang1_resolves, lang2_resolves], [Tool1, Tool2, Tool3], requested
        )
        assert user_resolves == expected_user_resolves
        assert tools == expected_tools

    assert_chosen(
        {Tool2.resolve_name, "u2"},
        expected_user_resolves=[Lang1Requested(["u2"])],
        expected_tools=[Tool2],
    )
    assert_chosen(
        {Tool1.resolve_name, Tool3.resolve_name},
        expected_user_resolves=[],
        expected_tools=[Tool1, Tool3],
    )

    # If none are specifically requested, return all.
    assert_chosen(
        set(),
        expected_user_resolves=[Lang1Requested(["u1", "u2"]), Lang2Requested(["u3"])],
        expected_tools=[Tool1, Tool2, Tool3],
    )

    with pytest.raises(UnrecognizedResolveNamesError):
        assert_chosen({"fake"}, expected_user_resolves=[], expected_tools=[])

    # Error if same resolve name used for tool lockfiles and user lockfiles.
    class AmbiguousTool(GenerateToolLockfileSentinel):
        resolve_name = "ambiguous"

    with pytest.raises(AmbiguousResolveNamesError):
        determine_resolves_to_generate(
            [
                KnownUserResolveNames(
                    ("ambiguous",),
                    "[lang].resolves",
                    requested_resolve_names_cls=Lang1Requested,
                )
            ],
            [AmbiguousTool],
            set(),
        )
    with pytest.raises(AmbiguousResolveNamesError):
        determine_resolves_to_generate(
            [
                KnownUserResolveNames(
                    ("ambiguous",),
                    "[lang1].resolves",
                    requested_resolve_names_cls=Lang1Requested,
                ),
                KnownUserResolveNames(
                    ("ambiguous",),
                    "[lang2].resolves",
                    requested_resolve_names_cls=Lang1Requested,
                ),
            ],
            [],
            set(),
        )


def test_filter_tool_lockfile_requests() -> None:
    def create_request(name: str, lockfile_dest: str | None = None) -> GenerateLockfile:
        return GenerateLockfile(resolve_name=name, lockfile_dest=lockfile_dest or f"{name}.txt")

    tool1 = create_request("tool1")
    tool2 = create_request("tool2")
    disabled_tool = create_request("none", lockfile_dest=NO_TOOL_LOCKFILE)
    default_tool = create_request("default", lockfile_dest=DEFAULT_TOOL_LOCKFILE)

    def assert_filtered(
        extra_request: GenerateLockfile | None,
        *,
        resolve_specified: bool,
    ) -> None:
        requests = [WrappedGenerateLockfile(tool1), WrappedGenerateLockfile(tool2)]
        if extra_request:
            requests.append(WrappedGenerateLockfile(extra_request))
        assert filter_tool_lockfile_requests(requests, resolve_specified=resolve_specified) == [
            tool1,
            tool2,
        ]

    assert_filtered(None, resolve_specified=False)
    assert_filtered(None, resolve_specified=True)

    assert_filtered(disabled_tool, resolve_specified=False)
    with pytest.raises(ValueError) as exc:
        assert_filtered(disabled_tool, resolve_specified=True)
    assert f"`[{disabled_tool.resolve_name}].lockfile` is set to `{NO_TOOL_LOCKFILE}`" in str(
        exc.value
    )

    assert_filtered(default_tool, resolve_specified=False)
    with pytest.raises(ValueError) as exc:
        assert_filtered(default_tool, resolve_specified=True)
    assert f"`[{default_tool.resolve_name}].lockfile` is set to `{DEFAULT_TOOL_LOCKFILE}`" in str(
        exc.value
    )


def test_no_compatible_resolve_error() -> None:
    python_setup = create_subsystem(PythonSetup, resolves={"a": "", "b": ""}, enable_resolves=True)
    t1 = PythonRequirementTarget(
        {
            PythonRequirementsField.alias: [],
            PythonResolveField.alias: "a",
            Dependencies.alias: ["//:t3"],
        },
        Address("", target_name="t1"),
    )
    t2 = PythonSourceTarget(
        {
            PythonSourceField.alias: "f.py",
            PythonResolveField.alias: "a",
            Dependencies.alias: ["//:t3"],
        },
        Address("", target_name="t2"),
    )
    t3 = PythonSourceTarget(
        {PythonSourceField.alias: "f.py", PythonResolveField.alias: "b"},
        Address("", target_name="t3"),
    )

    def maybe_get_resolve(t: Target) -> str | None:
        if not t.has_field(PythonResolveField):
            return None
        return t[PythonResolveField].normalized_value(python_setup)

    bad_roots_err = str(
        NoCompatibleResolveException.bad_input_roots(
            [t2, t3], maybe_get_resolve=maybe_get_resolve, doc_url_slug="", workaround=None
        )
    )
    assert bad_roots_err.startswith(
        softwrap(
            """
            The input targets did not have a resolve in common.

            a:
              * //:t2

            b:
              * //:t3

            Targets used together must use the same resolve, set by the `resolve` field.
            """
        )
    )

    bad_single_dep_err = str(
        NoCompatibleResolveException.bad_dependencies(
            maybe_get_resolve=maybe_get_resolve,
            doc_url_slug="",
            root_targets=[t1],
            root_resolve="a",
            dependencies=[t3],
        )
    )
    assert bad_single_dep_err.startswith(
        softwrap(
            """
            The target //:t1 uses the `resolve` `a`, but some of its
            dependencies are not compatible with that resolve:

              * //:t3 (b)

            All dependencies must work with the same `resolve`. To fix this, either change
            the `resolve=` field on those dependencies to `a`, or change
            the `resolve=` of the target //:t1.
            """
        )
    )

    bad_multiple_deps_err = str(
        NoCompatibleResolveException.bad_dependencies(
            maybe_get_resolve=maybe_get_resolve,
            doc_url_slug="",
            root_targets=[t1, t2],
            root_resolve="a",
            dependencies=[t3],
        )
    )
    assert bad_multiple_deps_err.startswith(
        softwrap(
            """
            The input targets use the `resolve` `a`, but some of their
            dependencies are not compatible with that resolve.

            Input targets:

              * //:t1
              * //:t2

            Bad dependencies:

              * //:t3 (b)

            All dependencies must work with the same `resolve`. To fix this, either change
            the `resolve=` field on those dependencies to `a`, or change
            the `resolve=` of the input targets.
            """
        )
    )


_default = "_default"


@pytest.mark.parametrize(
    ("env_names", "expected", "in_output", "not_in_output"),
    (
        ((), _default, None, "anything"),
        (("jeremy", "derek"), "jeremy", "`jeremy`, which may have ", None),
        (("jeremy", "_default"), "_default", "`_default`, which may have ", None),
        (("_default", "jeremy"), "_default", "`_default`, which may have ", None),
        (("jeremy",), "jeremy", None, "anything"),
    ),
)
def test_preferred_environment(
    env_names: Iterable[str],
    expected: str,
    in_output: str | None,
    not_in_output: str | None,
    caplog,
):

    resolve_name = "boop"
    resolve_dest = "beep"
    if not env_names:
        request = GenerateLockfile(resolve_name, resolve_dest)
    else:
        envs = tuple(EnvironmentName(name) for name in env_names)
        request = GenerateLockfileWithEnvironments(resolve_name, resolve_dest, envs)

    default = EnvironmentName(_default)

    preferred_env = _preferred_environment(request, default)

    assert preferred_env.val == expected
    assert in_output is None or in_output in caplog.text
    assert not_in_output is None or not_in_output not in caplog.text
