import argparse
import json
import pathlib
import shlex
import uuid


def write_scalar(output_path: pathlib.Path, name: str, value: str) -> None:
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def write_multiline(output_path: pathlib.Path, name: str, values: list[str]) -> None:
    delimiter = f"EOF_{name.upper()}_{uuid.uuid4().hex}"
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}<<{delimiter}\n")
        for value in values:
            handle.write(f"{value}\n")
        handle.write(f"{delimiter}\n")


def load_config(config_path: pathlib.Path) -> dict:
    if not config_path.is_file():
        raise SystemExit(f"缺少项目构建参数文件：{config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def export_rust_config(output_path: pathlib.Path, project_name: str, config: dict) -> None:
    rust_config = config.get("rust") or {}
    if not isinstance(rust_config, dict):
        raise SystemExit("build.public.json 中的 rust 段必须是对象。")

    binary_name = str(rust_config.get("binary_name") or project_name)
    asset_name = str(rust_config.get("asset_name") or f"{project_name}-windows-x64.zip")
    cargo_args = rust_config.get("cargo_args") or []
    artifact_files = rust_config.get("artifact_files") or []

    if not isinstance(cargo_args, list):
        raise SystemExit("rust.cargo_args 必须是数组。")
    if not isinstance(artifact_files, list):
        raise SystemExit("rust.artifact_files 必须是数组。")

    rust_args = shlex.join(["--release", *[str(item) for item in cargo_args]])

    write_scalar(output_path, "asset_name", asset_name)
    write_scalar(output_path, "rust_binary_name", binary_name)
    write_scalar(output_path, "rust_args", rust_args)
    write_scalar(
        output_path,
        "rust_artifact_files_json",
        json.dumps([str(item) for item in artifact_files], ensure_ascii=False),
    )


def export_python_config(output_path: pathlib.Path, project_name: str, config: dict) -> None:
    python_config = config.get("python") or {}
    if not isinstance(python_config, dict):
        raise SystemExit("build.public.json 中的 python 段必须是对象。")

    include_data_files = python_config.get("include_data_files") or []
    if not isinstance(include_data_files, list):
        raise SystemExit("python.include_data_files 必须是数组。")

    write_scalar(output_path, "asset_name", str(python_config.get("asset_name") or f"{project_name}-windows-x64.exe"))
    write_scalar(output_path, "python_entry_file", str(python_config.get("entry_file") or "main.py"))
    write_scalar(output_path, "python_mode", str(python_config.get("mode") or "onefile"))
    write_scalar(output_path, "python_output_file", str(python_config.get("output_filename") or f"{project_name}.exe"))
    write_scalar(output_path, "python_nuitka_version", str(python_config.get("nuitka_version") or "main"))
    write_scalar(output_path, "python_windows_icon_from_ico", str(python_config.get("windows_icon_from_ico") or ""))
    write_scalar(
        output_path,
        "python_assume_yes_for_downloads",
        str(bool(python_config.get("assume_yes_for_downloads", True))).lower(),
    )
    write_scalar(output_path, "python_file_description", str(python_config.get("file_description") or ""))
    write_scalar(output_path, "python_product_name", str(python_config.get("product_name") or ""))
    write_scalar(output_path, "python_company_name", str(python_config.get("company_name") or ""))
    write_scalar(output_path, "python_file_version", str(python_config.get("file_version") or ""))
    write_scalar(output_path, "python_product_version", str(python_config.get("product_version") or ""))
    write_scalar(output_path, "python_copyright", str(python_config.get("copyright") or ""))
    write_scalar(output_path, "python_trademarks", str(python_config.get("trademarks") or ""))
    write_multiline(output_path, "python_include_data_files", [str(item) for item in include_data_files])


def main() -> None:
    parser = argparse.ArgumentParser(description="Export build.public.json values to GITHUB_OUTPUT.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--project-language", required=True, choices=["rust", "python"])
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args()

    project_root = pathlib.Path(args.project_root)
    output_path = pathlib.Path(args.output_file)
    config = load_config(project_root / "build.public.json")

    if args.project_language == "rust":
        export_rust_config(output_path, args.project_name, config)
    else:
        export_python_config(output_path, args.project_name, config)


if __name__ == "__main__":
    main()
