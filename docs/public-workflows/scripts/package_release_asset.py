import argparse
import json
import pathlib
import shutil
import zipfile


def append_output(output_path: pathlib.Path, name: str, value: str) -> None:
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def package_rust_asset(
    source_root: pathlib.Path,
    project_root: pathlib.Path,
    runner_temp: pathlib.Path,
    asset_name: str,
    rust_binary_name: str,
    rust_artifact_files_json: str,
) -> pathlib.Path:
    release_dir = source_root / "target" / "release"
    if not release_dir.is_dir():
        raise SystemExit(f"Rust release 目录不存在：{release_dir}")

    binary_path = release_dir / f"{rust_binary_name}.exe"
    if not binary_path.exists():
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
