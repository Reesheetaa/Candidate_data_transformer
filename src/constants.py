"""Project-wide constants: source reliability, regexes, canonical skill map."""

from __future__ import annotations

# Reliability score per source, used as the base for confidence scoring.
SOURCE_RELIABILITY: dict[str, float] = {
    "csv": 0.95,
    "resume": 0.90,
    "notes": 0.75,
}

# Default region used when parsing phone numbers that have no country code.
# India is used because the sample data is India-centric (LPA salaries, +91 numbers).
DEFAULT_PHONE_REGION = "IN"

# Canonical skill dictionary. Keys are lowercase aliases, values are canonical names.
SKILL_CANONICAL_MAP: dict[str, str] = {
    "py": "Python",
    "python": "Python",
    "python3": "Python",
    "cpp": "C++",
    "c++": "C++",
    "c plus plus": "C++",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "aws": "AWS",
    "gcp": "Google Cloud Platform",
    "azure": "Azure",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "nlp": "Natural Language Processing",
    "ai": "Artificial Intelligence",
    "git": "Git",
    "linux": "Linux",
    "rest": "REST APIs",
    "restful": "REST APIs",
    "graphql": "GraphQL",
    "html": "HTML",
    "css": "CSS",
    "backend": "Backend Development",
    "back-end": "Backend Development",
    "frontend": "Frontend Development",
    "front-end": "Frontend Development",
    "fullstack": "Full Stack Development",
    "full stack": "Full Stack Development",
    "java": "Java",
    "golang": "Go",
    "go": "Go",
    "redis": "Redis",
    "kafka": "Apache Kafka",
    "spark": "Apache Spark",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
}

# Skill vocabulary scanned for in free text (resume / notes), in addition to whatever
# is already canonicalized via SKILL_CANONICAL_MAP. These are the canonical forms.
KNOWN_SKILLS: set[str] = set(SKILL_CANONICAL_MAP.values())

EMAIL_REGEX = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"

# Loosely matches international / Indian phone numbers with optional separators.
PHONE_REGEX = r"(\+?\d[\d\-\s()]{7,}\d)"

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

VALID_DEGREES = [
    "B.Tech", "B.E.", "B.Sc", "M.Tech", "M.E.", "M.Sc", "MBA", "BCA", "MCA",
    "Ph.D", "PhD", "Bachelor", "Master", "Diploma",
]
