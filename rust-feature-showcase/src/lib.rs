pub mod error;
pub mod model;
pub mod output;
pub mod pipeline;
pub mod scoring;

pub use error::{Result, ShowcaseError};
pub use model::{AnalysisReport, PlanSummary, Priority, ScoredItem, WorkItem, WorkPlan, WorkState};
pub use output::{render_report, OutputFormat};
pub use pipeline::{analyze_plan, load_plan, validate_plan};
