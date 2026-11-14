import argparse
import json
import pathlib
import shutil
import zipfile


def append_output(output_path: pathlib.Path, name: str, value: str) -> None:
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def read_rust_binary_name(project_root: pathlib.Path) -> str:
    """直接从 build.public.json 读取二进制名。

    该值可能包含中文（例如「保障通报」）。命令行参数在 Windows runner 上会丢失
    非 ASCII 字符，因此以配置文件为权威来源，参数只作为兜底。
    """
    config_path = project_root / "build.public.json"
    if not config_path.is_file():
        return ""

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""

    rust_config = config.get("rust")
    if not isinstance(rust_config, dict):
        return ""

    return str(rust_config.get("binary_name") or "")


def package_rust_asset(
    source_root: pathlib.Path,
    project_root: pathlib.Path,
    runner_temp: pathlib.Path,
    asset_name: str,
    rust_target: str,
    rust_binary_name: str,
    rust_artifact_files_json: str,
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

    staging_dir = runner_temp / f"{project_root.name}-staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(binary_path, staging_dir / binary_path.name)

    artifact_files = json.loads(rust_artifact_files_json or "[]")
    for relative_path in artifact_files:
        source_path = project_root / relative_path
        if not source_path.exists():
            raise SystemExit(f"找不到附加产物：{source_path}")

        target_path = staging_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, target_path)

    release_asset_path = runner_temp / asset_name
    if release_asset_path.exists():
        release_asset_path.unlink()

    with zipfile.ZipFile(release_asset_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(staging_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(staging_dir).as_posix())

    return release_asset_path


def package_python_asset(
    project_root: pathlib.Path,
    runner_temp: pathlib.Path,
    asset_name: str,
    python_output_file: str,
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

    release_asset_path = runner_temp / asset_name
    if release_asset_path.exists():
        release_asset_path.unlink()
    shutil.copy2(executable_path, release_asset_path)
    return release_asset_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Package build outputs for private release upload.")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--project-language", required=True, choices=["rust", "python"])
    parser.add_argument("--asset-name", required=True)
    parser.add_argument("--runner-temp", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--rust-target", default="")
    parser.add_argument("--rust-binary-name", default="")
    parser.add_argument("--rust-artifact-files-json", default="[]")
    parser.add_argument("--python-output-file", default="")
    args = parser.parse_args()

    source_root = pathlib.Path(args.source_root)
    project_root = source_root / pathlib.Path(args.project_path)
    runner_temp = pathlib.Path(args.runner_temp)
    output_path = pathlib.Path(args.output_file)

    if args.project_language == "rust":
        release_asset_path = package_rust_asset(
            source_root=source_root,
            project_root=project_root,
            runner_temp=runner_temp,
            asset_name=args.asset_name,
            rust_target=args.rust_target,
            rust_binary_name=args.rust_binary_name,
            rust_artifact_files_json=args.rust_artifact_files_json,
        )
    else:
        release_asset_path = package_python_asset(
            project_root=project_root,
            runner_temp=runner_temp,
            asset_name=args.asset_name,
            python_output_file=args.python_output_file,
        )

    append_output(output_path, "release_asset_path", release_asset_path.as_posix())


if __name__ == "__main__":
    main()
