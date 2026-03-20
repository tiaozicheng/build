use crate::error::{Result, ShowcaseError};
use crate::model::{AnalysisReport, PlanSummary, ScoredItem, WorkItem, WorkPlan, WorkState};
use crate::scoring::{default_strategies, score_item};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;
use std::sync::Arc;
use std::thread;

pub fn load_plan(path: &Path) -> Result<WorkPlan> {
    let raw = fs::read_to_string(path)?;
    let plan: WorkPlan = serde_json::from_str(&raw)?;
    validate_plan(&plan)?;
    Ok(plan)
}

pub fn validate_plan(plan: &WorkPlan) -> Result<()> {
    if plan.items.is_empty() {
        return Err(ShowcaseError::EmptyPlan);
    }

    let mut known_ids = HashSet::with_capacity(plan.items.len());
    for item in &plan.items {
        if !known_ids.insert(item.id.clone()) {
            return Err(ShowcaseError::DuplicateItemId(item.id.clone()));
        }
    }

    for item in &plan.items {
        for dependency in &item.blocked_by {
            if !known_ids.contains(dependency) {
                return Err(ShowcaseError::InvalidDependency {
                    item_id: item.id.clone(),
                    missing_id: dependency.clone(),
                });
            }
        }
    }

    Ok(())
}

pub fn analyze_plan(plan: &WorkPlan) -> Result<AnalysisReport> {
    let ranked_items = score_items_in_parallel(&plan.items)?;
    let summary = summarize(plan);
    let warnings = build_warnings(plan, &ranked_items);

    Ok(AnalysisReport {
        plan_name: plan.name.clone(),
        created_by: plan.created_by.clone(),
        item_count: plan.items.len(),
        ranked_items,
        summary,
        warnings,
    })
}

fn score_items_in_parallel(items: &[WorkItem]) -> Result<Vec<ScoredItem>> {
    if items.is_empty() {
        return Ok(Vec::new());
    }

    let strategies = Arc::new(default_strategies());
    let worker_count = thread::available_parallelism()
        .map(|value| value.get())
        .unwrap_or(1)
        .min(items.len())
        .max(1);
    let chunk_size = items.len().div_ceil(worker_count);
    let mut handles = Vec::with_capacity(worker_count);

    for chunk in items.chunks(chunk_size) {
        let local_items = chunk.to_vec();
        let local_strategies = Arc::clone(&strategies);
        handles.push(thread::spawn(move || {
            local_items
                .into_iter()
                .map(|item| score_item(&item, local_strategies.as_ref()))
                .collect::<Vec<_>>()
        }));
    }

    let mut ranked = Vec::with_capacity(items.len());
    for handle in handles {
        let mut batch = handle.join().map_err(|_| ShowcaseError::WorkerPanic)?;
        ranked.append(&mut batch);
    }

    ranked.sort_by(|left, right| {
        right
            .score
            .cmp(&left.score)
            .then_with(|| left.id.cmp(&right.id))
    });
    Ok(ranked)
}

fn summarize(plan: &WorkPlan) -> PlanSummary {
    let by_priority = group_count_by(&plan.items, |item| item.priority.to_string());
    let by_owner = group_count_by(&plan.items, |item| {
        item.owner
            .clone()
            .unwrap_or_else(|| "unassigned".to_string())
    });

    let mut tag_frequency = BTreeMap::new();
    for tag in plan.items.iter().flat_map(|item| item.tags.iter().cloned()) {
        *tag_frequency.entry(tag).or_insert(0) += 1;
    }

    let total_items = plan.items.len();
    let open_items = plan
        .items
        .iter()
        .filter(|item| !matches!(item.state, WorkState::Done))
        .count();
    let blocked_items = plan
        .items
        .iter()
        .filter(|item| matches!(item.state, WorkState::Blocked) || !item.blocked_by.is_empty())
        .count();

    PlanSummary {
        total_items,
        open_items,
        blocked_items,
        by_priority,
        by_owner,
        tag_frequency,
    }
}

fn build_warnings(plan: &WorkPlan, ranked_items: &[ScoredItem]) -> Vec<String> {
    let mut warnings = Vec::new();

    let critical_blocked = plan
        .items
        .iter()
        .filter(|item| item.priority.to_string() == "critical" && !item.blocked_by.is_empty())
        .count();
    if critical_blocked > 0 {
        warnings.push(format!(
            "{critical_blocked} critical items are blocked by unresolved dependencies"
        ));
    }

    if let Some(item) = ranked_items.first() {
        warnings.push(format!(
            "highest ranked item is '{}' with score {}",
            item.id, item.score
        ));
    }

    warnings
}

fn group_count_by<T, K, F>(items: &[T], key_fn: F) -> BTreeMap<K, usize>
where
    K: Ord,
    F: Fn(&T) -> K,
{
    let mut groups = BTreeMap::new();
    for item in items {
        *groups.entry(key_fn(item)).or_insert(0) += 1;
    }
    groups
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Priority, WorkItem, WorkPlan, WorkState};

    fn sample_plan() -> WorkPlan {
        WorkPlan {
            name: "demo".to_string(),
            created_by: "tests".to_string(),
            items: vec![
                WorkItem {
                    id: "setup".to_string(),
                    title: "Setup".to_string(),
                    owner: Some("alice".to_string()),
                    priority: Priority::Critical,
                    state: WorkState::Todo,
                    estimate_hours: 4,
                    tags: vec!["repo".to_string()],
                    blocked_by: Vec::new(),
                    notes: None,
                },
                WorkItem {
                    id: "report".to_string(),
                    title: "Report".to_string(),
                    owner: None,
                    priority: Priority::Medium,
                    state: WorkState::Blocked,
                    estimate_hours: 8,
                    tags: vec!["output".to_string()],
                    blocked_by: vec!["setup".to_string()],
                    notes: None,
                },
            ],
        }
    }

    #[test]
    fn validate_plan_rejects_missing_dependencies() {
        let mut plan = sample_plan();
        plan.items[1].blocked_by = vec!["missing".to_string()];
        let err = validate_plan(&plan).expect_err("missing dependency should fail");
        assert!(matches!(err, ShowcaseError::InvalidDependency { .. }));
    }

    #[test]
    fn analyze_plan_orders_items_by_score() {
        let report = analyze_plan(&sample_plan()).expect("analysis should succeed");
        assert_eq!(report.ranked_items[0].id, "setup");
    }

    #[test]
    fn summarize_counts_unassigned_owner() {
        let summary = summarize(&sample_plan());
        assert_eq!(summary.by_owner.get("unassigned"), Some(&1));
    }
}
