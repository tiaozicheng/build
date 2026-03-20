use clap::{Parser, Subcommand};
use rust_feature_showcase::{analyze_plan, load_plan, render_report, OutputFormat, Result};
use std::path::PathBuf;

#[derive(Parser)]
#[command(author, version, about = "A compact Rust feature showcase CLI.")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Analyze {
        #[arg(long, short)]
        input: PathBuf,
        #[arg(long, value_enum, default_value_t = OutputFormat::Text)]
        format: OutputFormat,
    },
    Validate {
        #[arg(long, short)]
        input: PathBuf,
    },
    PrintSample,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("error: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Analyze { input, format } => {
            let plan = load_plan(&input)?;
            let report = analyze_plan(&plan)?;
            println!("{}", render_report(&report, format)?);
        }
        Commands::Validate { input } => {
            let plan = load_plan(&input)?;
            println!(
                "plan '{}' is valid with {} items",
                plan.name,
                plan.items.len()
            );
        }
        Commands::PrintSample => {
            println!("{}", include_str!("../sample-data.json"));
        }
    }

    Ok(())
}
