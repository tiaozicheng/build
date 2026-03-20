use std::error::Error;
use std::fmt::{self, Display};
use std::io;

#[derive(Debug)]
pub enum ShowcaseError {
    Io(io::Error),
    Json(serde_json::Error),
    EmptyPlan,
    DuplicateItemId(String),
    InvalidDependency { item_id: String, missing_id: String },
    WorkerPanic,
}

impl Display for ShowcaseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(err) => write!(f, "io error: {err}"),
            Self::Json(err) => write!(f, "json error: {err}"),
            Self::EmptyPlan => write!(f, "the plan must contain at least one work item"),
            Self::DuplicateItemId(id) => write!(f, "duplicate work item id: {id}"),
            Self::InvalidDependency {
                item_id,
                missing_id,
            } => write!(
                f,
                "work item '{item_id}' depends on missing item '{missing_id}'"
            ),
            Self::WorkerPanic => write!(f, "a worker thread panicked while scoring items"),
        }
    }
}

impl Error for ShowcaseError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Io(err) => Some(err),
            Self::Json(err) => Some(err),
            Self::EmptyPlan
            | Self::DuplicateItemId(_)
            | Self::InvalidDependency { .. }
            | Self::WorkerPanic => None,
        }
    }
}

impl From<io::Error> for ShowcaseError {
    fn from(value: io::Error) -> Self {
        Self::Io(value)
    }
}

impl From<serde_json::Error> for ShowcaseError {
    fn from(value: serde_json::Error) -> Self {
        Self::Json(value)
    }
}

pub type Result<T> = std::result::Result<T, ShowcaseError>;
