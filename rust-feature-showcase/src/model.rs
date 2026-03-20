use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fmt::{self, Display};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Priority {
    Low,
    Medium,
    High,
    Critical,
}

impl Priority {
    pub fn weight(&self) -> i32 {
        match self {
            Self::Low => 1,
            Self::Medium => 3,
            Self::High => 6,
            Self::Critical => 10,
        }
    }
}

impl Display for Priority {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Low => f.write_str("low"),
            Self::Medium => f.write_str("medium"),
            Self::High => f.write_str("high"),
            Self::Critical => f.write_str("critical"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum WorkState {
    Todo,
    InProgress,
    Blocked,
    Done,
}

impl WorkState {
    pub fn weight(&self) -> i32 {
        match self {
            Self::Todo => 4,
            Self::InProgress => 6,
            Self::Blocked => 1,
            Self::Done => -2,
        }
    }
}

impl Display for WorkState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Todo => f.write_str("todo"),
            Self::InProgress => f.write_str("in_progress"),
            Self::Blocked => f.write_str("blocked"),
            Self::Done => f.write_str("done"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkItem {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub owner: Option<String>,
    pub priority: Priority,
    pub state: WorkState,
    pub estimate_hours: u32,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub blocked_by: Vec<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkPlan {
    pub name: String,
    pub created_by: String,
    pub items: Vec<WorkItem>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScoredItem {
    pub id: String,
    pub title: String,
    pub owner: Option<String>,
    pub priority: Priority,
    pub state: WorkState,
    pub score: i32,
    pub reasons: Vec<String>,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PlanSummary {
    pub total_items: usize,
    pub open_items: usize,
    pub blocked_items: usize,
    pub by_priority: BTreeMap<String, usize>,
    pub by_owner: BTreeMap<String, usize>,
    pub tag_frequency: BTreeMap<String, usize>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AnalysisReport {
    pub plan_name: String,
    pub created_by: String,
    pub item_count: usize,
    pub ranked_items: Vec<ScoredItem>,
    pub summary: PlanSummary,
    pub warnings: Vec<String>,
}
