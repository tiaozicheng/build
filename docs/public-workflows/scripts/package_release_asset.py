import argparse
import json
import pathlib
import shutil
import zipfile

# Windows 文件名非法字符。可执行文件名要落地成真实文件，含这些字符会直接失败，
# 提前拦下比等打包阶段报一个含糊的 OSError 更容易定位。
INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def append_output(output_path: pathlib.Path, name: str, value: str) -> None:
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def read_project_config(project_root: pathlib.Path) -> dict:
    config_path = project_root / "build.public.json"
    if not config_path.is_file():
        return {}

    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def read_rust_binary_name(project_root: pathlib.Path) -> str:
    """直接从 build.public.json 读取二进制名。

    该值可能包含中文（例如「保障通报」）。命令行参数在 Windows runner 上会丢失
    非 ASCII 字符，因此以配置文件为权威来源，参数只作为兜底。
    """
    rust_config = read_project_config(project_root).get("rust")
    if not isinstance(rust_config, dict):
        return ""

    return str(rust_config.get("binary_name") or "")


def read_python_display_name(project_root: pathlib.Path) -> str:
    """直接从 build.public.json 读取可执行文件中文名。

    与 Rust 的 binary_name 同理：中文名要落地成真实文件名，绝不能让非 ASCII
    经过 step output / 表达式插值链路，因此以配置文件为唯一权威来源。
    """
    python_config = read_project_config(project_root).get("python")
    if not isinstance(python_config, dict):
        return ""

    return str(python_config.get("display_name") or "")


def ensure_valid_executable_name(name: str) -> str:
    if not name or not name.strip():
        raise SystemExit("可执行文件名称为空，无法打包。")
    if name != name.strip():
        raise SystemExit(f"可执行文件名称首尾含空白：{name!r}")
    invalid = sorted({char for char in name if char in INVALID_FILENAME_CHARS})
    if invalid:
        raise SystemExit(f"可执行文件名称含非法字符 {''.join(invalid)}：{name!r}")
    return name


def zip_directory(staging_dir: pathlib.Path, release_asset_path: pathlib.Path) -> pathlib.Path:
    if release_asset_path.exists():
        release_asset_path.unlink()

    with zipfile.ZipFile(release_asset_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(staging_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(staging_dir).as_posix())

    return release_asset_path


def copy_artifact_files(
    project_root: pathlib.Path,
    staging_dir: pathlib.Path,
    artifact_files_json: str,
) -> None:
    """把需要随产物分发的文件或目录复制到 staging，与可执行文件同级。"""
    artifact_files = json.loads(artifact_files_json or "[]")
    for relative_path in artifact_files:
        source_path = project_root / relative_path
        if not source_path.exists():
            raise SystemExit(f"找不到附加产物：{source_path}")

        target_path = staging_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, target_path)


def package_rust_asset(
    source_root: pathlib.Path,
    project_root: pathlib.Path,
    runner_temp: pathlib.Path,
    asset_name: str,
    rust_target: str,
    rust_binary_name: str,
    rust_artifact_files_json: str,
    short_sha: str,
) -> pathlib.Path:
    release_dir_candidates = []
    target_roots = [project_root / "target", source_root / "target"]
    for target_root in target_roots:
        if rust_target:
            release_dir_candidates.append(target_root / rust_target / "release")
        release_dir_candidates.append(target_root / "release")

    release_dir = next((path for path in release_dir_candidates if path.is_dir()), None)
    if release_dir is None:
        candidates_text = "、".join(str(path) for path in release_dir_candidates)
        raise SystemExit(f"Rust release 目录不存在：{candidates_text}")

    config_binary_name = read_rust_binary_name(project_root)
    binary_names = [name for name in (config_binary_name, rust_binary_name) if name]

    binary_path = None
    for name in binary_names:
        candidate = release_dir / f"{name}.exe"
        if candidate.exists():
            binary_path = candidate
            break

    if binary_path is None:
        candidates = sorted(release_dir.glob("*.exe"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            raise SystemExit(f"未找到 Rust 可执行产物：{release_dir}")
        binary_path = candidates[0]

    executable_name = ensure_valid_executable_name(
        config_binary_name or rust_binary_name or binary_path.stem
    )

    staging_dir = runner_temp / f"{project_root.name}-staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # cargo 的 target 名是编译期固定的，无法带哈希；重命名放在打包阶段，
    # 让 zip 内的可执行文件与 Python 项目保持同一套「中文名_短hash」约定。
    shutil.copy2(binary_path, staging_dir / f"{executable_name}_{short_sha}.exe")

    copy_artifact_files(project_root, staging_dir, rust_artifact_files_json)

    return zip_directory(staging_dir, runner_temp / asset_name)


def package_python_asset(
    project_root: pathlib.Path,
    runner_temp: pathlib.Path,
    asset_name: str,
    python_output_file: str,
    python_artifact_files_json: str,
    short_sha: str,
) -> pathlib.Path:
    build_dir = project_root / "build"
    if not build_dir.is_dir():
        raise SystemExit(f"Nuitka build 目录不存在：{build_dir}")

    preferred_path = build_dir / python_output_file
    if preferred_path.exists():
        executable_path = preferred_path
    else:
        candidates = sorted(build_dir.glob("*.exe"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            raise SystemExit(f"未找到 Python 可执行产物：{build_dir}")
        executable_path = candidates[0]

    executable_name = ensure_valid_executable_name(
        read_python_display_name(project_root)
        or pathlib.Path(python_output_file).stem
        or project_root.name
    )

    # Python 产物同样走 zip：Release 资产名必须 ASCII，而可执行文件本身要中文名，
    # 只有把 exe 放进 zip 才能同时满足这两点。规则配置等需要用户维护的文件通过
    # artifact_files 一并打入 zip，与 exe 同级，而不是塞进 onefile 临时解压目录。
    staging_dir = runner_temp / f"{project_root.name}-staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(executable_path, staging_dir / f"{executable_name}_{short_sha}.exe")

    copy_artifact_files(project_root, staging_dir, python_artifact_files_json)

    return zip_directory(staging_dir, runner_temp / asset_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Package build outputs for private release upload.")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--project-language", required=True, choices=["rust", "python"])
    parser.add_argument("--asset-name", required=True)
    parser.add_argument("--runner-temp", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--rust-target", default="")
    parser.add_argument("--rust-binary-name", default="")
    parser.add_argument("--rust-artifact-files-json", default="[]")
    parser.add_argument("--python-output-file", default="")
    parser.add_argument("--python-artifact-files-json", default="[]")
    args = parser.parse_args()

    source_root = pathlib.Path(args.source_root)
    project_root = source_root / pathlib.Path(args.project_path)
    runner_temp = pathlib.Path(args.runner_temp)
    output_path = pathlib.Path(args.output_file)

    commit_sha = args.commit_sha.strip()
    if len(commit_sha) < 7:
        raise SystemExit(f"commit SHA 长度不足：{args.commit_sha!r}")
    # 与 scripts/ci/new_release_tag.sh 取同样的 7 位，保证文件名与 Release 标签对得上。
    short_sha = commit_sha[:7]

    if args.project_language == "rust":
        release_asset_path = package_rust_asset(
            source_root=source_root,
            project_root=project_root,
            runner_temp=runner_temp,
            asset_name=args.asset_name,
            rust_target=args.rust_target,
            rust_binary_name=args.rust_binary_name,
            rust_artifact_files_json=args.rust_artifact_files_json,
            short_sha=short_sha,
        )
    else:
        release_asset_path = package_python_asset(
            project_root=project_root,
            runner_temp=runner_temp,
            asset_name=args.asset_name,
            python_output_file=args.python_output_file,
            python_artifact_files_json=args.python_artifact_files_json,
            short_sha=short_sha,
        )

    append_output(output_path, "release_asset_path", release_asset_path.as_posix())


if __name__ == "__main__":
    main()
