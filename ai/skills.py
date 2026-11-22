ALIASES = {
    "apache airflow": "airflow",
    "microsoft azure": "azure",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "ruby on rails": "rails",
    "tailwind css": "tailwind",
    "hugging face": "huggingface",
    "llms": "llm",
    "large language models": "llm",
    "tanstack query": "tanstack",
    "tanstack router": "tanstack",
    "postgres": "postgresql",
    "js": "javascript",
    "k8s": "kubernetes",
    "golang": "go",
    "nodejs": "node.js",
    "node": "node.js",
    "nextjs": "next.js",
    "embedded linux": "linux",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "nuxt.js": "nuxt",
    "css3": "css",
    "html5": "html",
    "open telemetry": "opentelemetry",
    "hashicorp vault": "vault",
}

def normalize_skills(skills: list[str]) -> list[str]:
    """Lowercase, trim, rename to one standard name, and remove repeats."""
    clean = set()
    for skill in skills:
        name = skill.strip().lower()
        name = ALIASES.get(name, name)
        if name:
            clean.add(name)
    return sorted(clean)