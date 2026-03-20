use crate::model::{ScoredItem, WorkItem, WorkState};

pub trait ScoreStrategy: Send + Sync {
    fn label(&self) -> &'static str;
    fn score(&self, item: &WorkItem) -> i32;
}

pub struct PriorityStrategy;

impl ScoreStrategy for PriorityStrategy {
    fn label(&self) -> &'static str {
        "priority"
    }

    fn score(&self, item: &WorkItem) -> i32 {
        item.priority.weight() * 3
    }
}

pub struct StateStrategy;

impl ScoreStrategy for StateStrategy {
    fn label(&self) -> &'static str {
        "state"
    }

    fn score(&self, item: &WorkItem) -> i32 {
        item.state.weight() * 2
    }
}

pub struct SizeStrategy;

impl ScoreStrategy for SizeStrategy {
    fn label(&self) -> &'static str {
        "size"
    }

    fn score(&self, item: &WorkItem) -> i32 {
        match item.estimate_hours {
            0..=4 => 8,
            5..=12 => 5,
            13..=24 => 2,
            _ => -2,
        }
    }
}

pub struct DependencyStrategy;

impl ScoreStrategy for DependencyStrategy {
    fn label(&self) -> &'static str {
        "dependencies"
    }

    fn score(&self, item: &WorkItem) -> i32 {
        let dependency_penalty = (item.blocked_by.len() as i32) * 4;
        let blocked_penalty = if matches!(item.state, WorkState::Blocked) {
            6
        } else {
            0
        };

        -(dependency_penalty + blocked_penalty)
    }
}

pub fn default_strategies() -> Vec<Box<dyn ScoreStrategy>> {
    vec![
        Box::new(PriorityStrategy),
        Box::new(StateStrategy),
        Box::new(SizeStrategy),
        Box::new(DependencyStrategy),
    ]
}

pub fn score_item(item: &WorkItem, strategies: &[Box<dyn ScoreStrategy>]) -> ScoredItem {
    let mut score = 0;
    let mut reasons = Vec::with_capacity(strategies.len());

    for strategy in strategies {
        let partial = strategy.score(item);
        score += partial;
        reasons.push(format!("{}={partial}", strategy.label()));
    }

    ScoredItem {
        id: item.id.clone(),
        title: item.title.clone(),
        owner: item.owner.clone(),
        priority: item.priority.clone(),
        state: item.state.clone(),
        score,
        reasons,
        tags: item.tags.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Priority, WorkItem, WorkState};

    fn item_with(priority: Priority, state: WorkState) -> WorkItem {
        WorkItem {
            id: "item".to_string(),
            title: "Sample".to_string(),
            owner: Some("alice".to_string()),
            priority,
            state,
            estimate_hours: 8,
            tags: vec!["demo".to_string()],
            blocked_by: Vec::new(),
            notes: None,
        }
    }

    #[test]
    fn critical_items_score_higher_than_low_priority_items() {
        let strategies = default_strategies();
        let low = score_item(&item_with(Priority::Low, WorkState::Todo), &strategies);
        let critical = score_item(&item_with(Priority::Critical, WorkState::Todo), &strategies);
        assert!(critical.score > low.score);
    }
}
