# build

公开构建仓库，保留通用构建工作流，并包含一个可直接构建的 Rust 示例工程，避免仓库成为只承载 Actions 的空壳。

## 保留的工作流

- `.github/workflows/build-python.yml`
- `.github/workflows/build-rust.yml`

## Rust 示例工程

- `rust-feature-showcase/`

该示例工程覆盖 Rust 的核心语言与工程能力，包括：

- `clap` 命令行入口和子命令
- `struct`、`enum`、`match`
- trait、泛型、trait object
- `serde` / `serde_json`
- 标准库线程并发
- 自定义错误类型
- 测试

## 使用方式

```powershell
cd rust-feature-showcase
cargo run -- print-sample
cargo run -- analyze --input sample-data.json
cargo test
```

