from typing import TypedDict, List, Dict


class AssignmentState(TypedDict, total=False):
    assignment_id: str
    project_id: str
    concept_ids: List[str]  # concept ID strings (strict project scope)
    concept_names: List[str]  # resolved names for prompts
    title: str
    num_questions: int
    answers: Dict[str, str]  # {question_id: selected_option} — present only on grade path
    score: float
    total: int
    error: str  # set when a node fails
