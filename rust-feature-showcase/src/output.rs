use crate::error::Result;
use crate::model::AnalysisReport;
use clap::ValueEnum;

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum OutputFormat {
    Text,
    Json,
}

pub fn render_report(report: &AnalysisReport, format: OutputFormat) -> Result<String> {
    match format {
        OutputFormat::Text => Ok(render_text(report)),
        OutputFormat::Json => Ok(serde_json::to_string_pretty(report)?),
    }
}

fn render_text(report: &AnalysisReport) -> String {
    let mut output = String::new();
    output.push_str(&format!(
        "Plan: {}\nCreated by: {}\nItems: {}\n\n",
        report.plan_name, report.created_by, report.item_count
    ));

    output.push_str("Summary\n");
    output.push_str(&format!(
        "- total: {}\n- open: {}\n- blocked: {}\n\n",
        report.summary.total_items, report.summary.open_items, report.summary.blocked_items
    ));

    output.push_str("Top ranked items\n");
    for item in report.ranked_items.iter().take(5) {
        output.push_str(&format!(
            "- {} [{} / {}] score={} reasons={}\n",
            item.id,
            item.priority,
            item.state,
            item.score,
            item.reasons.join(", ")
        ));
    }

    if !report.warnings.is_empty() {
        output.push_str("\nWarnings\n");
        for warning in &report.warnings {
            output.push_str(&format!("- {warning}\n"));
        }
    }

    output
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{AnalysisReport, PlanSummary, Priority, ScoredItem, WorkState};
    use std::collections::BTreeMap;

    #[test]
    fn render_text_contains_headings() {
        let report = AnalysisReport {
            plan_name: "demo".to_string(),
            created_by: "tests".to_string(),
            item_count: 1,
            ranked_items: vec![ScoredItem {
                id: "setup".to_string(),
                title: "Setup".to_string(),
                owner: Some("alice".to_string()),
                priority: Priority::High,
                state: WorkState::Todo,
                score: 42,
                reasons: vec!["priority=18".to_string()],
                tags: vec!["repo".to_string()],
            }],
            summary: PlanSummary {
                total_items: 1,
                open_items: 1,
                blocked_items: 0,
                by_priority: BTreeMap::new(),
                by_owner: BTreeMap::new(),
                tag_frequency: BTreeMap::new(),
            },
            warnings: vec!["demo warning".to_string()],
        };

        let rendered = render_report(&report, OutputFormat::Text).expect("text render should work");
        assert!(rendered.contains("Top ranked items"));
        assert!(rendered.contains("Warnings"));
    }
}
