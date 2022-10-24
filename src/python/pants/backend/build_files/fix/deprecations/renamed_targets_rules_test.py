# Copyright 2022 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest

from pants.backend.build_files.fix.deprecations.renamed_targets_rules import (
    RenameRequest,
    RenameTargetsInFileRequest,
    fix_single,
)


@pytest.mark.parametrize(
    "lines",
    (
        # Already valid.
        ["new_name()"],
        ["new_name ( ) "],
        ["new_name(foo)"],
        ["new_name(", "", ")"],
        # Unrelated lines.
        ["", "123", "target()", "name='new_name'"],
        # Ignore indented
        ["  new_name()"],
    ),
)
def test_rename_deprecated_target_types_noops(lines: list[str]) -> None:
    content = "\n".join(lines).encode("utf-8")
    result = fix_single(
        RenameRequest("BUILD", content=content),
        RenameTargetsInFileRequest({"deprecated_name": "new_name"}),
    )
    assert result.content == content


@pytest.mark.parametrize(
    "lines,expected",
    (
        (["deprecated_name()"], ["new_name()"]),
        (["deprecated_name ( ) "], ["new_name ( ) "]),
        (["deprecated_name()  # comment"], ["new_name()  # comment"]),
        (["deprecated_name(", "", ")"], ["new_name(", "", ")"]),
    ),
)
def test_rename_deprecated_target_types_rewrite(lines: list[str], expected: list[str]) -> None:
    result = fix_single(
        RenameRequest("BUILD", content="\n".join(lines).encode("utf-8")),
        RenameTargetsInFileRequest({"deprecated_name": "new_name"}),
    )
    assert result.content == "\n".join(expected).encode("utf-8")
